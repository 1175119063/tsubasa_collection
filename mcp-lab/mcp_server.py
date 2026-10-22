"""A minimal MCP stdio server exposing read-only iNaturalist tools.

Protocol notes that matter on Windows:

* stdio messages are newline-delimited UTF-8 JSON; binary stdio is used so
  Python never translates "\\n" into "\\r\\n";
* stdout carries protocol traffic only, every log line goes to stderr;
* notifications (messages without an ``id``) are never answered;
* the client's requested protocol version is echoed when supported.
"""

from __future__ import annotations

import json
import logging
import sys
import traceback

import inat_api

SERVER_NAME = "tsubasa-inat-lab"
SERVER_VERSION = "0.1.0"
SUPPORTED_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")
DEFAULT_VERSION = SUPPORTED_VERSIONS[0]

LOG = logging.getLogger("inat-mcp")


class RpcError(Exception):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


TOOLS = [
    {
        "name": "search_taxa",
        "title": "Search iNaturalist taxa",
        "description": (
            "Search iNaturalist for taxa. Reliable for scientific names and English "
            "common names. Chinese free-text queries return fuzzy taxonomic noise, so "
            "prefer resolve_name for Chinese names."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "minLength": 1},
                "locale": {"type": "string", "default": "zh-CN"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5},
                "rank": {"type": "string", "description": "Optional rank filter, e.g. species"},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "openWorldHint": True},
    },
    {
        "name": "get_taxon",
        "title": "Get iNaturalist taxon detail",
        "description": (
            "Read one taxon by id: ancestors, order/family/genus, Wikipedia summary, "
            "conservation status and the licence/attribution of the default photo."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "taxon_id": {"type": "integer", "minimum": 1},
                "locale": {"type": "string", "default": "zh-CN"},
            },
            "required": ["taxon_id"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "openWorldHint": True},
    },
    {
        "name": "resolve_name",
        "title": "Resolve a Chinese or scientific name",
        "description": (
            "Resolve one name to a single verified taxon. Order: local alias -> exact "
            "iNaturalist match -> Wikidata taxon name (P225) -> exact common-name match. "
            "Returns resolved=false with candidates instead of guessing."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "minLength": 1},
                "locale": {"type": "string", "default": "zh-CN"},
                "use_aliases": {"type": "boolean", "default": True},
                "allow_wikidata": {"type": "boolean", "default": True},
            },
            "required": ["name"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "openWorldHint": True},
    },
]


def _send(message: dict) -> None:
    payload = json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    sys.stdout.buffer.write(payload + b"\n")
    sys.stdout.buffer.flush()


def _error(message_id: object, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": message_id, "error": {"code": code, "message": message}}


def _tool_result(payload: object, is_error: bool = False) -> dict:
    return {
        "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}],
        "isError": is_error,
    }


def _require_string(arguments: dict, key: str) -> str:
    value = arguments.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RpcError(-32602, f"argument {key!r} must be a non-empty string")
    return value.strip()


def _optional_int(arguments: dict, key: str, default: int, low: int, high: int) -> int:
    value = arguments.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise RpcError(-32602, f"argument {key!r} must be an integer")
    return max(low, min(high, value))


def _optional_bool(arguments: dict, key: str, default: bool) -> bool:
    value = arguments.get(key, default)
    if not isinstance(value, bool):
        raise RpcError(-32602, f"argument {key!r} must be a boolean")
    return value


def dispatch_tool(name: str, arguments: dict) -> object:
    if name == "search_taxa":
        return inat_api.search_taxa(
            _require_string(arguments, "query"),
            locale=str(arguments.get("locale") or "zh-CN"),
            limit=_optional_int(arguments, "limit", 5, 1, 20),
            rank=arguments.get("rank") or None,
        )
    if name == "get_taxon":
        if "taxon_id" not in arguments:
            raise RpcError(-32602, "argument 'taxon_id' is required")
        return inat_api.get_taxon(
            arguments["taxon_id"],
            locale=str(arguments.get("locale") or "zh-CN"),
        )
    if name == "resolve_name":
        return inat_api.resolve_name(
            _require_string(arguments, "name"),
            locale=str(arguments.get("locale") or "zh-CN"),
            use_aliases=_optional_bool(arguments, "use_aliases", True),
            allow_wikidata=_optional_bool(arguments, "allow_wikidata", True),
        )
    raise RpcError(-32602, f"unknown tool: {name}")


def call_tool(params: dict) -> dict:
    if not isinstance(params, dict):
        raise RpcError(-32602, "tools/call params must be an object")
    name = params.get("name")
    if not isinstance(name, str) or not name:
        raise RpcError(-32602, "tools/call requires a tool name")
    arguments = params.get("arguments") or {}
    if not isinstance(arguments, dict):
        raise RpcError(-32602, "tools/call arguments must be an object")
    try:
        return _tool_result(dispatch_tool(name, arguments), False)
    except inat_api.InatError as exc:
        LOG.warning("tool %s failed: %s", name, exc)
        return _tool_result(
            {"error": {"type": "inat_error", "message": str(exc), "status": exc.status}},
            True,
        )
    except Exception as exc:  # keep the server alive for the next request
        LOG.error("tool %s crashed: %s\n%s", name, exc, traceback.format_exc())
        return _tool_result(
            {"error": {"type": "internal_error", "message": str(exc)}},
            True,
        )


def handle_request(message: dict) -> None:
    message_id = message.get("id")
    method = message.get("method")
    params = message.get("params") or {}
    if method == "initialize":
        requested = str((params or {}).get("protocolVersion") or "")
        version = requested if requested in SUPPORTED_VERSIONS else DEFAULT_VERSION
        if requested and requested != version:
            LOG.info("protocol %s unsupported, negotiating %s", requested, version)
        result = {
            "protocolVersion": version,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            "instructions": (
                "Read-only iNaturalist lookup for a personal field journal. "
                "Suggestions must be shown to the user before any field is written."
            ),
        }
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        result = call_tool(params)
    else:
        raise RpcError(-32601, f"method not found: {method}")
    _send({"jsonrpc": "2.0", "id": message_id, "result": result})


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    LOG.info("%s %s ready", SERVER_NAME, SERVER_VERSION)
    while True:
        raw = sys.stdin.buffer.readline()
        if not raw:
            break
        try:
            message = json.loads(raw.decode("utf-8", "replace"))
        except json.JSONDecodeError:
            _send(_error(None, -32700, "parse error"))
            continue
        if not isinstance(message, dict) or not isinstance(message.get("method"), str):
            _send(_error(None, -32600, "invalid request"))
            continue
        if "id" not in message:
            LOG.debug("notification: %s", message.get("method"))
            continue
        try:
            handle_request(message)
        except RpcError as exc:
            _send(_error(message.get("id"), exc.code, exc.message))
        except Exception as exc:
            LOG.error("request crashed: %s\n%s", exc, traceback.format_exc())
            _send(_error(message.get("id"), -32603, "internal error"))
    LOG.info("stdin closed, exiting")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
