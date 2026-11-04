"""Read-only tests for the species-profile completion skill."""

from pathlib import Path

import pytest
from app.assistant_schemas import (
    AssistantSpeciesProfileDraft,
    SpeciesProfileChunkReview,
)
from app.config import Settings
from app.feather_assistant import FeatherAssistantError
from app.inat_mcp import inat_api
from app.main import create_app
from app.skills.base import SkillError
from app.skills.species_profile import SpeciesProfileSkill
from fastapi.testclient import TestClient


class _FakeAssistant:
    def __init__(
        self,
        result: AssistantSpeciesProfileDraft | None = None,
        error: Exception | None = None,
        review_results: list[SpeciesProfileChunkReview] | None = None,
        review_error: Exception | None = None,
    ) -> None:
        self.result = result or AssistantSpeciesProfileDraft(
            introduction="整合后的物种简介。"
        )
        self.error = error
        self.review_results = list(review_results or [])
        self.review_error = review_error
        self.evidence: dict | None = None
        self.reviews: list[dict] = []

    def review_species_profile_chunk(self, evidence: dict) -> SpeciesProfileChunkReview:
        self.reviews.append(evidence)
        if self.review_error is not None:
            raise self.review_error
        if not self.review_results:
            raise AssertionError("unexpected profile review")
        return self.review_results.pop(0)

    def draft_species_profile(self, evidence: dict) -> AssistantSpeciesProfileDraft:
        self.evidence = evidence
        if self.error is not None:
            raise self.error
        return self.result


def _taxon() -> dict:
    return {
        "id": 1,
        "name": "Cyanopica cyanus",
        "common_name": "灰喜鹊",
        "english_common_name": "Azure-winged Magpie",
        "rank": "species",
        "is_bird": True,
        "is_active": True,
        "classification": {
            "order": {"name": "Passeriformes", "common_name": "雀形目"},
            "family": {"name": "Corvidae", "common_name": "鸦科"},
            "genus": {"name": "Cyanopica", "common_name": "灰喜鹊属"},
        },
        "wikipedia_url": "https://zh.wikipedia.org/wiki/%E7%81%B0%E5%96%9C%E9%B9%8A",
        "summary": "灰喜鹊是鸦科灰喜鹊属的鸟类。",
        "url": "https://www.inaturalist.org/taxa/1",
        "conservation": [],
    }


def _wiki() -> dict:
    return {
        "available": True,
        "title": "灰喜鹊",
        "url": "https://zh.wikipedia.org/wiki/%E7%81%B0%E5%96%9C%E9%B9%8A",
        "excerpt": "灰喜鹊分布于东亚，常见于城市公园和校园。",
        "extract": "灰喜鹊分布于东亚，常见于城市公园和校园。",
        "fetched_at": "2026-11-04T00:00:00+08:00",
    }


def _resolved(taxon: dict | None = None) -> dict:
    return {
        "resolved": taxon is not None,
        "taxon": taxon,
        "candidates": [],
        "via": "test",
        "wikidata": None,
        "warnings": [],
    }


class _FakeProfile:
    def __init__(self, result: dict) -> None:
        self.result = result
        self.calls: list[tuple[str, str | None, str]] = []

    def draft(
        self,
        scientific_name: str,
        chinese_name: str | None,
        introduction: str,
    ) -> dict:
        self.calls.append((scientific_name, chinese_name, introduction))
        return self.result


def test_species_profile_endpoint_uses_current_introduction_and_does_not_save(
    tmp_path: Path,
) -> None:
    app = create_app(
        Settings(_env_file=None, data_dir=tmp_path, online_species_enabled=True)
    )
    result = {
        "introduction": "灰喜鹊常成群活动，我在校园里见过它在树上跳跃。",
        "warnings": [],
        "sources": [{"title": "iNaturalist", "url": "https://www.inaturalist.org/taxa/1"}],
    }
    fake = _FakeProfile(result)
    with TestClient(app) as client:
        app.state.species_profile = fake
        database = tmp_path / "database.sqlite"
        before = database.read_bytes()
        response = client.post(
            "/api/assistant/species-profile",
            json={
                "scientific_name": "Cyanopica cyanus",
                "chinese_name": "灰喜鹊",
                "introduction": "我在校园里看到它。",
            },
        )
        assert response.status_code == 200
        assert response.json() == result
        assert fake.calls == [("Cyanopica cyanus", "灰喜鹊", "我在校园里看到它。")]
        assert database.read_bytes() == before


def test_species_profile_skill_integrates_current_introduction_and_wikipedia(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(inat_api, "resolve_name", lambda *a, **kw: _resolved(_taxon()))
    assistant = _FakeAssistant(
        AssistantSpeciesProfileDraft(
            introduction="灰喜鹊常成群活动；我在校园里见过它在树上跳跃。"
        )
    )
    skill = SpeciesProfileSkill(assistant=assistant)
    skill.online._wiki_fetcher = lambda **kw: _wiki()

    result = skill.draft("Cyanopica cyanus", "灰喜鹊", "我在校园里见过它在树上跳跃。")

    assert result["introduction"] == "灰喜鹊常成群活动；我在校园里见过它在树上跳跃。"
    assert assistant.evidence is not None
    assert assistant.evidence["existing_introduction"] == "我在校园里见过它在树上跳跃。"
    assert "分布" in assistant.evidence["wikipedia"]["excerpt"]
    assert {source["title"] for source in result["sources"]} == {
        "iNaturalist",
        "Wikipedia",
    }
    assert assistant.reviews == []


def test_species_profile_loops_over_long_input_until_ai_has_enough(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(inat_api, "resolve_name", lambda *a, **kw: _resolved(_taxon()))
    existing = "我在校园里见过灰喜鹊。" * 400
    wiki = _wiki()
    wiki["excerpt"] = "灰喜鹊分布于东亚，常见于城市公园和校园。" * 200
    assistant = _FakeAssistant(
        review_results=[
            SpeciesProfileChunkReview(
                notes=["校园观察：灰喜鹊常在树上跳跃。"],
                enough=False,
                missing="分布与栖息地",
            ),
            SpeciesProfileChunkReview(
                notes=["分布：东亚的城市公园与校园。"],
                enough=True,
            ),
        ]
    )
    skill = SpeciesProfileSkill(assistant=assistant)
    skill.online._wiki_fetcher = lambda **kw: wiki

    result = skill.draft("Cyanopica cyanus", "灰喜鹊", existing)

    assert len(assistant.reviews) == 2
    assert assistant.reviews[0]["chunk"]["index"] == 1
    assert len(assistant.reviews[0]["chunk"]["text"]) <= 3000
    assert assistant.evidence is not None
    research = assistant.evidence["research"]
    assert research["chunks_read"] == 2
    assert research["chunks_total"] >= 2
    assert research["stopped"] == "enough"
    assert research["input_chars"] == len(existing) + len(wiki["excerpt"][:4000])
    assert assistant.evidence["research_notes"] == [
        "校园观察：灰喜鹊常在树上跳跃。",
        "分布：东亚的城市公园与校园。",
    ]
    assert assistant.evidence["existing_introduction"] == ""
    assert result["introduction"] == "整合后的物种简介。"
    assert any("较长" in warning for warning in result["warnings"])


def test_species_profile_review_failure_does_not_overwrite(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(inat_api, "resolve_name", lambda *a, **kw: _resolved(_taxon()))
    assistant = _FakeAssistant(review_error=FeatherAssistantError("模型离线"))
    skill = SpeciesProfileSkill(assistant=assistant)
    skill.online._wiki_fetcher = lambda **kw: _wiki()

    with pytest.raises(SkillError) as error:
        skill.draft("Cyanopica cyanus", "灰喜鹊", "长简介" * 2000)

    assert error.value.status_code == 503
    assert "模型离线" in error.value.message


def test_species_profile_skill_rejects_unresolved_species(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(inat_api, "resolve_name", lambda *a, **kw: _resolved(None))
    skill = SpeciesProfileSkill(assistant=_FakeAssistant())

    with pytest.raises(SkillError) as error:
        skill.draft("Unknown bird", None, "旧简介")

    assert error.value.status_code == 404


def test_species_profile_skill_returns_503_when_ai_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(inat_api, "resolve_name", lambda *a, **kw: _resolved(_taxon()))
    skill = SpeciesProfileSkill(
        assistant=_FakeAssistant(error=FeatherAssistantError("模型离线"))
    )
    skill.online._wiki_fetcher = lambda **kw: _wiki()

    with pytest.raises(SkillError) as error:
        skill.draft("Cyanopica cyanus", "灰喜鹊", "旧简介")

    assert error.value.status_code == 503
    assert "模型离线" in error.value.message


def test_species_profile_endpoint_rejects_blank_scientific_name(tmp_path: Path) -> None:
    app = create_app(Settings(_env_file=None, data_dir=tmp_path))
    with TestClient(app) as client:
        response = client.post(
            "/api/assistant/species-profile",
            json={"scientific_name": " ", "introduction": "旧简介"},
        )
    assert response.status_code == 422


def test_species_profile_endpoint_maps_skill_errors(tmp_path: Path) -> None:
    class _BrokenProfile:
        def draft(self, *args) -> dict:
            raise SkillError("资料不足，简介没有修改。", 502)

    app = create_app(Settings(_env_file=None, data_dir=tmp_path))
    with TestClient(app) as client:
        app.state.species_profile = _BrokenProfile()
        response = client.post(
            "/api/assistant/species-profile",
            json={"scientific_name": "Cyanopica cyanus", "introduction": "旧简介"},
        )
    assert response.status_code == 502
    assert response.json()["detail"] == "资料不足，简介没有修改。"


def test_assistant_profile_prompt_includes_existing_introduction(monkeypatch) -> None:
    from app.feather_assistant import FeatherAssistant

    assistant = FeatherAssistant(Settings(_env_file=None))
    captured: dict[str, str] = {}

    def fake_chat(system, user, response_model, temperature=0.1, timeout=None):
        captured["system"] = system
        captured["user"] = user
        return AssistantSpeciesProfileDraft(introduction="整合后的简介。")

    monkeypatch.setattr(assistant, "_chat", fake_chat)
    result = assistant.draft_species_profile(
        {
            "existing_introduction": "我在校园里见过它。",
            "wikipedia": {"excerpt": "灰喜鹊常见于城市公园。"},
        }
    )

    assert result.introduction == "整合后的简介。"
    assert "现有简介" in captured["system"]
    assert "我在校园里见过它。" in captured["user"]
    assert "灰喜鹊常见于城市公园。" in captured["user"]


def test_profile_external_model_gets_enough_output_budget(monkeypatch) -> None:
    from app.feather_assistant import FeatherAssistant

    assistant = FeatherAssistant(Settings(_env_file=None))
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        assistant,
        "_external_config",
        lambda require_selected=True: {
            "provider": "openai_compatible",
            "base_url": "https://example.invalid/v1",
            "api_key": "test",
            "model": "reasoning-model",
        },
    )

    def fake_request(config, messages, temperature, max_tokens, timeout=None):
        captured["max_tokens"] = max_tokens
        return '{"introduction":"整理后的简介。","warnings":[]}'

    monkeypatch.setattr(assistant, "_request_openai_chat", fake_request)
    result = assistant.draft_species_profile({"existing_introduction": "旧简介"})

    assert result.introduction == "整理后的简介。"
    assert captured["max_tokens"] >= 2400
