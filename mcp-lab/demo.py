"""End-to-end demo: iNaturalist API -> MCP stdio -> client.

Run:  python demo.py
Out:  artifacts/demo_report.json, artifacts/transcript.jsonl, artifacts/taxon_62148.json
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

import inat_api
from mcp_client import McpStdioClient, McpToolError

LAB_DIR = Path(__file__).resolve().parent
ARTIFACTS = LAB_DIR / "artifacts"
SAMPLE_SCIENTIFIC = "Chlidonias hybrida"
SAMPLE_CHINESE = "灰翅浮鸥"
SAMPLE_TAXON_ID = 62148


def ascii_json(value: object, limit: int = 160) -> str:
    text = json.dumps(value, ensure_ascii=True, separators=(",", ":"))
    return text if len(text) <= limit else text[: limit - 3] + "..."


def short_taxon(taxon: dict) -> str:
    return (
        f"#{taxon.get('id')} {taxon.get('name')} "
        f"/ {ascii_json(taxon.get('common_name'), 60)} ({taxon.get('rank')})"
    )


def main() -> int:
    ARTIFACTS.mkdir(exist_ok=True)
    report: dict = {"generated_at": datetime.now().astimezone().isoformat(timespec="seconds")}
    steps: list[dict] = report.setdefault("steps", [])

    # 1. Scientific-name search is the reliable path.
    started = time.perf_counter()
    search = inat_api.search_taxa(SAMPLE_SCIENTIFIC)
    elapsed = time.perf_counter() - started
    steps.append({"step": "inat_search_scientific", "result": search})
    print(
        f"[1] iNat scientific search: total={search['total_results']} "
        f"top={short_taxon(search['results'][0])} "
        f"({elapsed:.2f}s, cached={search['cached']})"
    )

    # 2. Chinese free text is fuzzy noise on iNaturalist.
    zh = inat_api.search_taxa(SAMPLE_CHINESE)
    match, _field = inat_api._exact_match(zh["results"], SAMPLE_CHINESE)
    top_names = [item.get("name") for item in zh["results"][:5]]
    steps.append(
        {
            "step": "inat_search_chinese",
            "total": zh["total_results"],
            "exact_match_in_top5": bool(match),
            "top_names": top_names,
        }
    )
    print(
        f"[2] iNat Chinese free text: total={zh['total_results']} "
        f"exact_match_in_top5={bool(match)} top={ascii_json(top_names)}"
    )

    # 3. Resolve a Chinese name without a local alias (Wikidata P225 bridge).
    started = time.perf_counter()
    resolved = inat_api.resolve_name(SAMPLE_CHINESE, use_aliases=False)
    cold = time.perf_counter() - started
    started = time.perf_counter()
    inat_api.resolve_name(SAMPLE_CHINESE, use_aliases=False)
    warm = time.perf_counter() - started
    steps.append(
        {
            "step": "resolve_without_alias",
            "resolved": resolved["resolved"],
            "via": resolved["via"],
            "scientific_name_used": resolved["scientific_name_used"],
            "cold_seconds": round(cold, 2),
            "warm_seconds": round(warm, 2),
            "warnings": resolved["warnings"],
        }
    )
    if resolved["resolved"]:
        print(
            f"[3] resolve {SAMPLE_CHINESE} (no alias): via={resolved['via']} "
            f"sci={resolved['scientific_name_used']} "
            f"-> {short_taxon(resolved['taxon'])} (cold={cold:.2f}s warm={warm:.2f}s)"
        )
    else:
        print(f"[3] resolve {SAMPLE_CHINESE} (no alias): FAILED {ascii_json(resolved['warnings'])}")

    # 4. Resolve through the archive's own alias table (if it has been built).
    aliases = inat_api.load_aliases()
    if aliases:
        alias_key = sorted(aliases)[0]
        alias_resolved = inat_api.resolve_name(alias_key, use_aliases=True)
        steps.append(
            {
                "step": "resolve_with_local_alias",
                "alias": alias_key,
                "alias_count": len(aliases),
                "resolved": alias_resolved["resolved"],
                "via": alias_resolved["via"],
                "scientific_name_used": alias_resolved["scientific_name_used"],
            }
        )
        state = "resolved" if alias_resolved["resolved"] else "not resolved"
        print(
            f"[4] local alias table: {len(aliases)} entries; "
            f"{ascii_json(alias_key)} -> {alias_resolved['scientific_name_used']} ({state}, "
            f"via={alias_resolved['via']})"
        )
    else:
        print("[4] local alias table: missing (run build_aliases.py)")

    # 5. MCP handshake, tool discovery, calls, tool error.
    started = time.perf_counter()
    with McpStdioClient() as client:
        tools = client.list_tools()
        print(
            f"[5] MCP handshake: protocol={client.protocol_version} "
            f"server={client.server_info.get('name')} tools={[tool['name'] for tool in tools]}"
        )
        mcp_search = client.call_tool_json(
            "search_taxa", {"query": SAMPLE_SCIENTIFIC, "limit": 5}
        )
        print(
            f"[6] MCP search_taxa: total={mcp_search['total_results']} "
            f"top={short_taxon(mcp_search['results'][0])} cached={mcp_search['cached']}"
        )
        mcp_resolve = client.call_tool_json(
            "resolve_name", {"name": SAMPLE_CHINESE, "use_aliases": False}
        )
        detail = client.call_tool_json("get_taxon", {"taxon_id": SAMPLE_TAXON_ID})
        print(
            f"[7] MCP resolve_name: resolved={mcp_resolve['resolved']} via={mcp_resolve['via']}"
        )
        print(
            f"[8] MCP get_taxon: order={detail['classification']['order']['name']} "
            f"family={detail['classification']['family']['name']} "
            f"genus={detail['classification']['genus']['name']} "
            f"photo_license={detail['photo']['license']}"
        )
        error_payload = None
        try:
            client.call_tool_json("get_taxon", {"taxon_id": 999_999_999})
        except McpToolError as exc:
            error_payload = exc.payload
        print(f"[9] MCP tool error path: {ascii_json(error_payload)}")
        elapsed = time.perf_counter() - started
        report["mcp"] = {
            "protocol_version": client.protocol_version,
            "server_info": client.server_info,
            "tools": tools,
            "search": mcp_search,
            "resolve": mcp_resolve,
            "taxon": detail,
            "tool_error": error_payload,
            "elapsed_seconds": round(elapsed, 2),
        }
        transcript = list(client.transcript)

    (ARTIFACTS / "demo_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (ARTIFACTS / "taxon_62148.json").write_text(
        json.dumps(report["mcp"]["taxon"], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with (ARTIFACTS / "transcript.jsonl").open("w", encoding="utf-8") as handle:
        for entry in transcript:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(f"\n[10] artifacts: {ARTIFACTS} ({len(transcript)} MCP messages recorded)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
