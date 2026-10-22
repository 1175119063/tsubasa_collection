"""Offline tests for the MCP lab (no network unless LAB_ONLINE=1)."""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import threading
import unittest

import inat_api
from mcp_client import (
    McpProcessError,
    McpRpcError,
    McpStdioClient,
    McpTimeout,
    McpToolError,
)

LAB_DIR = pathlib.Path(__file__).resolve().parent
FIXTURES = LAB_DIR / "fixtures"
PYTHON = sys.executable
ONLINE = os.environ.get("LAB_ONLINE") == "1"


def fake_client(mode: str) -> McpStdioClient:
    return McpStdioClient(
        [PYTHON, "-u", str(LAB_DIR / "fake_server.py")],
        env={"FAKE_MODE": mode},
    )


def read_line(stream, timeout: float = 8.0) -> bytes:
    box: dict[str, bytes] = {}
    thread = threading.Thread(target=lambda: box.update(line=stream.readline()), daemon=True)
    thread.start()
    thread.join(timeout)
    if thread.is_alive():
        raise TimeoutError("no line from server")
    return box.get("line", b"")


class ProtocolTests(unittest.TestCase):
    def test_real_server_handshake_and_tool_list(self) -> None:
        with McpStdioClient() as client:
            self.assertEqual(client.protocol_version, "2025-06-18")
            self.assertEqual(client.server_info.get("name"), "tsubasa-inat-lab")
            tools = client.list_tools()
            names = [tool["name"] for tool in tools]
            self.assertEqual(names, ["search_taxa", "get_taxon", "resolve_name"])
            for tool in tools:
                self.assertTrue(tool["annotations"]["readOnlyHint"])
                self.assertEqual(tool["inputSchema"]["type"], "object")

    def test_real_server_does_not_answer_notifications(self) -> None:
        process = subprocess.Popen(
            [PYTHON, "-u", str(LAB_DIR / "mcp_server.py")],
            cwd=str(LAB_DIR),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"},
        )
        try:
            assert process.stdin and process.stdout
            initialize = {
                "jsonrpc": "2.0",
                "id": 0,
                "method": "initialize",
                "params": {"protocolVersion": "2025-06-18", "capabilities": {}},
            }
            process.stdin.write(json.dumps(initialize).encode() + b"\n")
            process.stdin.flush()
            first = json.loads(read_line(process.stdout))
            self.assertEqual(first["id"], 0)

            notification = {"jsonrpc": "2.0", "method": "notifications/initialized"}
            process.stdin.write(json.dumps(notification).encode() + b"\n")
            process.stdin.flush()
            request = {"jsonrpc": "2.0", "id": 7, "method": "tools/list", "params": {}}
            process.stdin.write(json.dumps(request).encode() + b"\n")
            process.stdin.flush()
            second = json.loads(read_line(process.stdout))
            self.assertEqual(second["id"], 7, "server must stay silent for notifications")
            self.assertIn("tools", second["result"])
        finally:
            process.kill()
            process.wait(timeout=5)
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream:
                    stream.close()

    def test_unknown_method_is_a_rpc_error(self) -> None:
        with McpStdioClient() as client:
            with self.assertRaises(McpRpcError) as caught:
                client.request("does/not/exist", {}, timeout=5)
            self.assertEqual(caught.exception.code, -32601)


class ClientTests(unittest.TestCase):
    def test_client_calls_tools_on_fake_server(self) -> None:
        with fake_client("normal") as client:
            tools = client.list_tools()
            self.assertEqual([tool["name"] for tool in tools], ["echo", "fail"])
            payload = client.call_tool_json("echo", {"value": "灰翅浮鸥"})
            self.assertEqual(payload, {"value": "灰翅浮鸥"})

    def test_tool_error_is_surfaced(self) -> None:
        with fake_client("normal") as client:
            with self.assertRaises(McpToolError) as caught:
                client.call_tool_json("fail", {})
            self.assertEqual(caught.exception.payload, {"error": "boom"})

    def test_unknown_tool_is_a_rpc_error(self) -> None:
        with fake_client("normal") as client:
            with self.assertRaises(McpRpcError) as caught:
                client.call_tool("nope", {}, timeout=5)
            self.assertEqual(caught.exception.code, -32602)

    def test_timeout_kills_the_server(self) -> None:
        client = fake_client("silent")
        client.start()
        try:
            with self.assertRaises(McpTimeout):
                client.request("ping", {}, timeout=0.8)
            self.assertFalse(client.alive)
        finally:
            client.close()

    def test_crash_is_reported(self) -> None:
        client = fake_client("crash")
        client.start()
        try:
            with self.assertRaises(McpProcessError):
                client.request("ping", {}, timeout=3)
        finally:
            client.close()


class NormalizationTests(unittest.TestCase):
    def test_taxon_fixture_maps_classification_and_licence(self) -> None:
        payload = json.loads((FIXTURES / "taxon_62148_zh.json").read_text(encoding="utf-8"))
        taxon = inat_api.normalize_taxon(
            payload["results"][0], fetched_at="2026-10-22T00:00:00+08:00", cached=False
        )
        self.assertEqual(taxon["name"], "Chlidonias hybrida")
        self.assertEqual(taxon["id"], 62148)
        self.assertEqual(taxon["classification"]["order"]["name"], "Charadriiformes")
        self.assertEqual(taxon["classification"]["family"]["name"], "Laridae")
        self.assertEqual(taxon["classification"]["genus"]["name"], "Chlidonias")
        self.assertEqual(len(taxon["ancestors"]), 8)
        self.assertIn("须浮鸥", taxon["summary"] or "")
        self.assertNotIn("<b>", taxon["summary"] or "")
        self.assertEqual(taxon["photo"]["license"], "cc-by-nc")
        self.assertEqual(taxon["source_url"], "https://api.inaturalist.org/v1/taxa/62148")

    def test_exact_match_rejects_fuzzy_hits(self) -> None:
        results = [
            {"id": 1, "name": "Pterygota", "common_name": "有翅亚纲", "is_active": True},
            {"id": 2, "name": "Chlidonias hybrida", "common_name": "灰翅浮鸥", "is_active": True},
        ]
        self.assertEqual(inat_api._exact_match(results, "浮鸥"), (None, None))
        self.assertEqual(inat_api._exact_match(results, "灰翅浮鸥")[0]["id"], 2)
        self.assertEqual(inat_api._exact_match(results, "Chlidonias hybrida")[0]["id"], 2)

    def test_inactive_taxon_is_never_accepted(self) -> None:
        results = [{"id": 3, "name": "Old name", "is_active": False}]
        self.assertEqual(inat_api._exact_match(results, "Old name"), (None, None))


@unittest.skipUnless(ONLINE, "set LAB_ONLINE=1 to call the live API")
class OnlineTests(unittest.TestCase):
    def test_scientific_search_hits_the_expected_taxon(self) -> None:
        result = inat_api.search_taxa("Chlidonias hybrida", use_cache=False)
        self.assertGreaterEqual(result["total_results"], 1)
        self.assertEqual(result["results"][0]["id"], 62148)

    def test_taxon_detail_has_ancestors_and_summary(self) -> None:
        taxon = inat_api.get_taxon(62148, use_cache=False)
        self.assertEqual(taxon["classification"]["family"]["name"], "Laridae")
        self.assertTrue(taxon["summary"])

    def test_chinese_name_resolves_through_wikidata(self) -> None:
        result = inat_api.resolve_name("灰翅浮鸥", use_aliases=False, use_cache=False)
        self.assertTrue(result["resolved"])
        self.assertIn(result["via"], {"wikidata", "inat-common-name"})
        self.assertEqual(result["taxon"]["id"], 62148)


if __name__ == "__main__":
    unittest.main(verbosity=2)
