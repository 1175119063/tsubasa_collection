"""Minimal MCP stdio client used to exercise the lab server.

It deliberately implements the wire protocol by hand (newline-delimited
JSON-RPC 2.0 over the child process pipes) so the experiment shows what the
protocol actually does.  Two Windows-specific details are handled here:

* stderr is drained by a background thread, otherwise a chatty server fills
  the pipe buffer and deadlocks;
* stdout is read as bytes and split on ``b"\\n"`` so no newline translation
  can corrupt the framing.
"""

from __future__ import annotations

import json
import os
import pathlib
import queue
import subprocess
import sys
import threading
import time

LAB_DIR = pathlib.Path(__file__).resolve().parent
CLIENT_PROTOCOL = "2025-06-18"
CLIENT_INFO = {"name": "tsubasa-mcp-lab-client", "version": "0.1.0"}


class McpError(RuntimeError):
    pass


class McpTimeout(McpError):
    pass


class McpProcessError(McpError):
    pass


class McpRpcError(McpError):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(f"JSON-RPC error {code}: {message}")
        self.code = code
        self.rpc_message = message


class McpToolError(McpError):
    def __init__(self, payload: object) -> None:
        super().__init__("tool returned isError=true")
        self.payload = payload


class McpStdioClient:
    def __init__(
        self,
        command: list[str] | None = None,
        *,
        cwd: pathlib.Path | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        self.command = command or [sys.executable, "-u", str(LAB_DIR / "mcp_server.py")]
        self.cwd = cwd or LAB_DIR
        self.env = env or {}
        self.protocol_version: str | None = None
        self.server_info: dict = {}
        self.server_instructions: str | None = None
        self.transcript: list[dict] = []
        self._process: subprocess.Popen[bytes] | None = None
        self._messages: queue.Queue[dict | None] = queue.Queue()
        self._stderr_lines: list[str] = []
        self._next_id = 0
        self._threads: list[threading.Thread] = []

    # -- lifecycle ---------------------------------------------------------
    def start(self) -> None:
        if self._process is not None:
            raise McpError("client already started")
        environment = {
            **os.environ,
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUTF8": "1",
            **self.env,
        }
        self._process = subprocess.Popen(
            self.command,
            cwd=str(self.cwd),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=environment,
            bufsize=0,
        )
        self._threads = [
            threading.Thread(target=self._read_stdout, name="mcp-stdout", daemon=True),
            threading.Thread(target=self._read_stderr, name="mcp-stderr", daemon=True),
        ]
        for thread in self._threads:
            thread.start()

    def close(self, timeout: float = 5.0) -> None:
        process = self._process
        self._process = None
        if process is None:
            return
        try:
            if process.stdin:
                process.stdin.close()
        except OSError:
            pass
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=timeout)
        for thread in self._threads:
            thread.join(timeout=2)
        for stream in (process.stdout, process.stderr):
            if stream is not None:
                try:
                    stream.close()
                except OSError:
                    pass

    def restart(self) -> None:
        self.close()
        self._messages = queue.Queue()
        self.start()
        self.initialize()

    @property
    def alive(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def __enter__(self) -> McpStdioClient:
        self.start()
        self.initialize()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    # -- protocol ----------------------------------------------------------
    def initialize(self, timeout: float = 10.0) -> dict:
        result = self.request(
            "initialize",
            {
                "protocolVersion": CLIENT_PROTOCOL,
                "capabilities": {"roots": {"listChanged": False}},
                "clientInfo": CLIENT_INFO,
            },
            timeout=timeout,
        )
        self.protocol_version = str(result.get("protocolVersion") or "")
        self.server_info = result.get("serverInfo") or {}
        self.server_instructions = result.get("instructions")
        self.notify("notifications/initialized")
        return result

    def notify(self, method: str, params: dict | None = None) -> None:
        message: dict = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            message["params"] = params
        self._send(message)

    def request(self, method: str, params: dict | None = None, timeout: float = 20.0) -> dict:
        message_id = self._next_id
        self._next_id += 1
        message: dict = {"jsonrpc": "2.0", "id": message_id, "method": method}
        if params is not None:
            message["params"] = params
        self._send(message)
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                self._abort()
                raise McpTimeout(f"no response to {method!r} within {timeout}s")
            try:
                incoming = self._messages.get(timeout=remaining)
            except queue.Empty:
                self._abort()
                raise McpTimeout(f"no response to {method!r} within {timeout}s") from None
            if incoming is None:
                code = self._process.poll() if self._process else None
                raise McpProcessError(
                    f"server closed stdout (exit={code}); stderr={self.stderr_tail()}"
                )
            if incoming.get("id") != message_id:
                continue  # stray notification or late response
            if "error" in incoming:
                error = incoming.get("error") or {}
                raise McpRpcError(int(error.get("code", -1)), str(error.get("message", "")))
            return incoming.get("result") or {}

    def list_tools(self, timeout: float = 10.0) -> list[dict]:
        result = self.request("tools/list", {}, timeout=timeout)
        return list(result.get("tools") or [])

    def call_tool(
        self,
        name: str,
        arguments: dict | None = None,
        timeout: float = 30.0,
    ) -> dict:
        return self.request(
            "tools/call",
            {"name": name, "arguments": arguments or {}},
            timeout=timeout,
        )

    def call_tool_json(
        self,
        name: str,
        arguments: dict | None = None,
        timeout: float = 30.0,
    ) -> object:
        result = self.call_tool(name, arguments, timeout=timeout)
        payload = self._first_text(result)
        if result.get("isError"):
            raise McpToolError(payload)
        return payload

    @staticmethod
    def _first_text(result: dict) -> object:
        for block in result.get("content") or []:
            if isinstance(block, dict) and block.get("type") == "text":
                try:
                    return json.loads(block.get("text") or "null")
                except json.JSONDecodeError:
                    return block.get("text")
        return None

    # -- internals ---------------------------------------------------------
    def _send(self, message: dict) -> None:
        process = self._process
        if process is None or process.stdin is None:
            raise McpProcessError("client is not running")
        if process.poll() is not None:
            raise McpProcessError(f"server already exited (code={process.returncode})")
        payload = json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self._record("out", message)
        try:
            process.stdin.write(payload + b"\n")
            process.stdin.flush()
        except OSError as exc:
            raise McpProcessError(f"cannot write to server: {exc}") from exc

    def _record(self, direction: str, message: dict) -> None:
        if len(self.transcript) < 200:
            self.transcript.append({"dir": direction, "message": message})

    def _read_stdout(self) -> None:
        process = self._process
        if process is None or process.stdout is None:
            return
        for raw in iter(process.stdout.readline, b""):
            text = raw.decode("utf-8", "replace").strip()
            if not text:
                continue
            try:
                message = json.loads(text)
            except json.JSONDecodeError:
                self._stderr_lines.append(f"non-JSON on stdout: {text[:200]}")
                continue
            if isinstance(message, dict):
                self._record("in", message)
                self._messages.put(message)
        self._messages.put(None)

    def _read_stderr(self) -> None:
        process = self._process
        if process is None or process.stderr is None:
            return
        for raw in iter(process.stderr.readline, b""):
            line = raw.decode("utf-8", "replace").rstrip()
            if line:
                self._stderr_lines.append(line)
                if len(self._stderr_lines) > 200:
                    del self._stderr_lines[:100]

    def _abort(self) -> None:
        process = self._process
        if process is not None and process.poll() is None:
            process.kill()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass

    def stderr_tail(self, limit: int = 8) -> str:
        return " | ".join(self._stderr_lines[-limit:])
