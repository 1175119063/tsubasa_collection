"""Offline regressions for the real MCP transport and online assistant boundary."""

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock

import pytest
from app.config import Settings
from app.inat_mcp import inat_api
from app.inat_mcp.mcp_client import McpError, McpRpcError, McpStdioClient, McpTimeout
from app.main import create_app
from app.online_species_service import OnlineSpeciesService
from app.service_common import DomainError
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]


def fixture_taxon():
    payload = json.loads((ROOT / "mcp-lab/fixtures/taxon_62148_zh.json").read_text("utf-8"))
    return inat_api.normalize_taxon(
        payload["results"][0],
        fetched_at="2026-10-23T08:00:00+08:00",
        cached=False,
    )


@pytest.mark.parametrize(
    "name,args",
    [
        ("unknown", {}),
        ("get_taxon", {"taxon_id": True}),
        ("get_taxon", {"taxon_id": 1.5}),
        ("get_taxon", {"taxon_id": 0}),
        ("get_taxon", {"taxon_id": "123"}),
        ("get_taxon", {"taxon_id": 1, "extra": 1}),
        ("search_taxa", {"query": "bird", "limit": 99}),
        ("search_taxa", {"query": "bird", "locale": 3}),
        ("resolve_name", {"name": "bird", "use_aliases": "false"}),
    ],
)
def test_real_server_invalid_arguments_are_rpc_errors(name, args):
    with McpStdioClient() as client:
        with pytest.raises(McpRpcError) as error:
            client.call_tool_json(name, args)
        assert error.value.code == -32602
        assert client.request("ping") == {}  # Invalid calls do not kill the server.


def test_real_transport_reads_cache_and_does_not_call_network(tmp_path):
    taxon = fixture_taxon()
    key = inat_api._cache_key("taxon", {"kind": "taxon", "id": 62148, "locale": "zh-CN"})
    (tmp_path / f"{key}.json").write_text(json.dumps(taxon), encoding="utf-8")
    with McpStdioClient(env={"TSUBASA_INAT_CACHE_DIR": str(tmp_path)}) as client:
        result = client.call_tool_json("get_taxon", {"taxon_id": 62148})
    assert result["cached"] is True
    assert result["classification"]["family"]["name"] == "Laridae"


def test_client_serializes_simultaneous_requests():
    with McpStdioClient([sys.executable, str(ROOT / "mcp-lab/fake_server.py")]) as client:
        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(
                executor.map(lambda n: client.call_tool_json("echo", {"n": n}), range(30))
            )
    assert results == [{"n": n} for n in range(30)]


def test_failed_initialize_closes_process(monkeypatch):
    client = McpStdioClient()

    def fail():
        raise McpError("bad handshake")

    monkeypatch.setattr(client, "initialize", fail)
    with pytest.raises(McpError), client:
        pass
    assert not client.alive


def test_unsupported_protocol_is_rejected(monkeypatch):
    client = McpStdioClient()
    monkeypatch.setattr(client, "request", lambda *a, **kw: {"protocolVersion": "2099-01-01"})
    with pytest.raises(McpError, match="unsupported protocol"):
        client.initialize()


def test_same_common_name_is_not_a_unique_match():
    items = [
        {"id": n, "name": f"Bird {n}", "common_name": "同名鸟", "is_active": True} for n in (1, 2)
    ]
    assert inat_api._exact_match(items, "同名鸟") == (None, None)
    assert inat_api._exact_match([items[0], items[0]], "同名鸟")[0]["id"] == 1


def test_wikidata_does_not_accept_unrelated_first_hit(monkeypatch):
    monkeypatch.setattr(
        inat_api,
        "wikidata_candidates",
        lambda n: [
            {"qid": "Q1", "label": "不相关的鸟", "description": "bird species"},
        ],
    )
    claim = Mock(return_value="Pica serica")
    monkeypatch.setattr(inat_api, "wikidata_taxon_name", claim)
    assert inat_api.wikidata_resolution("灰翅浮鸥", use_cache=False)["scientific_name"] is None
    claim.assert_not_called()


def test_wikidata_exact_alias_is_accepted_but_homonyms_are_not(monkeypatch):
    candidates = [{"qid": "Q1", "label": "另一名称", "matched_text": "灰翅浮鸥"}]
    monkeypatch.setattr(inat_api, "wikidata_candidates", lambda n: candidates)
    monkeypatch.setattr(inat_api, "wikidata_taxon_name", lambda q: "Chlidonias hybrida")
    assert inat_api.wikidata_resolution("灰翅浮鸥", use_cache=False)["scientific_name"]
    candidates.append({"qid": "Q2", "label": "灰翅浮鸥"})
    assert inat_api.wikidata_resolution("灰翅浮鸥", use_cache=False)["scientific_name"] is None


def test_wikidata_failure_falls_back_to_inat(monkeypatch):
    monkeypatch.setattr(
        inat_api, "wikidata_resolution", Mock(side_effect=inat_api.InatError("503"))
    )
    taxon = fixture_taxon()
    taxon["common_name"] = "灰翅浮鸥"
    search = Mock(return_value={"results": [taxon], "total_results": 1})
    monkeypatch.setattr(inat_api, "search_taxa", search)
    monkeypatch.setattr(inat_api, "get_taxon", lambda *a, **kw: taxon)
    result = inat_api.resolve_name("灰翅浮鸥", use_aliases=False, use_cache=False)
    assert result["resolved"] and result["warnings"]
    search.assert_called_once()


def test_cache_failure_does_not_lose_network_result(monkeypatch, tmp_path):
    blocked = tmp_path / "not-a-directory"
    blocked.write_text("x")
    monkeypatch.setattr(inat_api, "CACHE_DIR", blocked)
    monkeypatch.setattr(inat_api, "_get_json", lambda url: {"results": [], "total_results": 0})
    assert inat_api.search_taxa("nothing")["results"] == []


def test_service_uses_mcp_and_cache_with_no_llm(tmp_path):
    service = OnlineSpeciesService(tmp_path)
    service.cache_dir.mkdir(parents=True)
    taxon = fixture_taxon()
    key = inat_api._cache_key("taxon", {"kind": "taxon", "id": 62148, "locale": "zh-CN"})
    (service.cache_dir / f"{key}.json").write_text(json.dumps(taxon), encoding="utf-8")
    detail = service.detail(62148)
    assert detail["draft"]["species"]["scientific_name"] == "Chlidonias hybrida"
    assert detail["cached"]


def test_service_rejects_non_birds_and_does_not_invent_chinese_names(monkeypatch, tmp_path):
    service = OnlineSpeciesService(tmp_path)
    taxon = fixture_taxon()
    taxon["common_name"] = "Whiskered Tern"
    monkeypatch.setattr(service, "_call", lambda *a: taxon)
    assert service.detail(62148)["draft"]["species"]["chinese_name"] is None
    taxon["is_bird"] = False
    with pytest.raises(DomainError) as exc:
        service.detail(62148)
    assert exc.value.status_code == 422


def test_service_timeout_releases_lock(monkeypatch, tmp_path):
    service = OnlineSpeciesService(tmp_path)
    monkeypatch.setattr(McpStdioClient, "call_tool_json", Mock(side_effect=McpTimeout("late")))
    with pytest.raises(DomainError) as exc:
        service.search("Pica serica")
    assert exc.value.status_code == 504
    assert service._lock.acquire(blocking=False)
    service._lock.release()


def test_http_boundary_validates_input_and_disable(tmp_path):
    app = create_app(Settings(_env_file=None, data_dir=tmp_path, online_species_enabled=False))
    with TestClient(app) as client:
        assert client.get("/api/assistant/online-species/status").json()["available"] is False
        assert (
            client.post("/api/assistant/online-species/search", json={"query": ""}).status_code
            == 422
        )
        assert client.get("/api/assistant/online-species/0").status_code == 422
        response = client.post("/api/assistant/online-species/search", json={"query": "喜鹊"})
        assert response.status_code == 503


def test_ambiguous_chinese_name_keeps_scientific_candidates(monkeypatch):
    monkeypatch.setattr(
        inat_api,
        "wikidata_resolution",
        lambda *a, **kw: {
            "candidates": [
                {"qid": "Q1", "label": "喜鹊", "scientific_name": "Pica serica"},
                {"qid": "Q2", "label": "喜鹊", "scientific_name": "Pica pica"},
            ],
            "fetched_at": "2026-10-23",
            "cached": False,
        },
    )

    def search(query, **kwargs):
        assert query != "喜鹊", "Do not replace scientific candidates with fuzzy Chinese results"
        return {
            "results": [
                {"id": 1 if query == "Pica serica" else 2, "name": query, "is_active": True}
            ]
        }

    monkeypatch.setattr(inat_api, "search_taxa", search)
    result = inat_api.resolve_name("喜鹊", use_aliases=False, use_cache=False)
    assert not result["resolved"]
    assert [item["name"] for item in result["candidates"]] == ["Pica serica", "Pica pica"]
    assert result["candidates"][0]["name_source"]["source_url"].endswith("Q1")


def test_packaging_launcher_exposes_protocol_without_starting_app():
    with McpStdioClient(
        [sys.executable, str(ROOT / "packaging/launcher.py"), "--inat-mcp"]
    ) as client:
        assert client.server_info["name"] == "tsubasa-inat"
        assert len(client.list_tools()) == 3


def test_client_restart_discards_closed_session_messages():
    with McpStdioClient() as client:
        for _ in range(3):
            assert len(client.list_tools()) == 3
            client.restart()
        assert client.request("ping") == {}
