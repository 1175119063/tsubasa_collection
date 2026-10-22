"""Scriptable fake MCP server for client/protocol tests (no network).

FAKE_MODE:
  normal  - standard handshake, two tools: echo / fail
  silent  - reads but never answers (timeout test)
  crash   - exits immediately with status 3
  badline - writes a non-JSON line before answering normally
"""

from __future__ import annotations

import json
import os
import sys

MODE = os.environ.get("FAKE_MODE", "normal")


def send(message: dict) -> None:
    sys.stdout.buffer.write(
        json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n"
    )
    sys.stdout.buffer.flush()


TOOLS = [
    {
        "name": "echo",
        "description": "Echo the arguments back.",
        "inputSchema": {
            "type": "object",
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "fail",
        "description": "Always returns isError=true.",
        "inputSchema": {"type": "object", "properties": {}},
        "annotations": {"readOnlyHint": True},
    },
]


def main() -> int:
    if MODE == "crash":
        return 3
    if MODE == "badline":
        sys.stdout.buffer.write(b"this is not json\n")
        sys.stdout.buffer.flush()
    while True:
        raw = sys.stdin.buffer.readline()
        if not raw:
            return 0
        try:
            message = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            continue
        if MODE == "silent":
            continue
        method = message.get("method")
        if "id" not in message:
            continue
        message_id = message.get("id")
        try:
            if method == "initialize":
                result = {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "fake", "version": "0.0.1"},
                }
            elif method == "ping":
                result = {}
            elif method == "tools/list":
                result = {"tools": TOOLS}
            elif method == "tools/call":
                params = message.get("params") or {}
                name = params.get("name")
                arguments = params.get("arguments") or {}
                if name == "echo":
                    result = {
                        "content": [
                            {"type": "text", "text": json.dumps(arguments, ensure_ascii=False)}
                        ],
                        "isError": False,
                    }
                elif name == "fail":
                    result = {
                        "content": [{"type": "text", "text": json.dumps({"error": "boom"})}],
                        "isError": True,
                    }
                else:
                    send(
                        {
                            "jsonrpc": "2.0",
                            "id": message_id,
                            "error": {"code": -32602, "message": f"unknown tool: {name}"},
                        }
                    )
                    continue
            else:
                send(
                    {
                        "jsonrpc": "2.0",
                        "id": message_id,
                        "error": {"code": -32601, "message": "method not found"},
                    }
                )
                continue
        except Exception as exc:  # noqa: BLE001 - the fake server must stay alive
            send(
                {
                    "jsonrpc": "2.0",
                    "id": message_id,
                    "error": {"code": -32603, "message": str(exc)},
                }
            )
            continue
        send({"jsonrpc": "2.0", "id": message_id, "result": result})


if __name__ == "__main__":
    raise SystemExit(main())
