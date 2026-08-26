import json

import pytest
from app.assistant_catalog import normalized_lookup, resolve_catalog_item
from app.assistant_schemas import AssistantChatMessage
from app.config import Settings
from app.feather_assistant import FeatherAssistant, FeatherAssistantError
from app.main import create_app
from fastapi.testclient import TestClient


class StubAssistant(FeatherAssistant):
    def __init__(self, responses: list[dict]) -> None:
        super().__init__(
            Settings(
                _env_file=None,
                feather_assistant_base_url="http://127.0.0.1:11434",
                feather_assistant_model="feiyu-jingling",
            )
        )
        self.responses = responses
        self.requests: list[tuple[str, dict | None]] = []

    def _request_json(self, path: str, payload: dict | None = None) -> dict:
        self.requests.append((path, payload))
        return self.responses.pop(0)


class ExternalConfig:
    def get_llm(self) -> dict:
        return {
            "provider": "openai_compatible",
            "base_url": "https://example.com/v1",
            "model": "external-model",
            "api_key": "secret-key",
        }


class HybridAssistant(StubAssistant):
    def __init__(self, responses: list[dict]) -> None:
        super().__init__(responses)
        self.integration_store = ExternalConfig()
        self.external_requests: list[tuple[dict, list[dict], float, int]] = []

    def _request_openai_chat(
        self,
        config: dict,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> str:
        self.external_requests.append((config, messages, temperature, max_tokens))
        return "探险家，当然可以聊聊迁徙路线。"


def chat_response(value: dict) -> dict:
    return {"message": {"content": json.dumps(value, ensure_ascii=False)}}


def test_status_accepts_latest_alias() -> None:
    assistant = StubAssistant([{"models": [{"name": "feiyu-jingling:latest"}]}])

    result = assistant.status()

    assert result["available"] is True
    assert result["model"] == "feiyu-jingling"
    assert assistant.requests == [("/api/tags", None)]


def test_status_recommends_external_provider_for_local_model_under_8b() -> None:
    assistant = StubAssistant(
        [
            {
                "models": [
                    {
                        "name": "feiyu-jingling:latest",
                        "details": {"parameter_size": "2.2B"},
                    }
                ]
            }
        ]
    )

    result = assistant.status()

    assert result["parameter_size"] == "2.2B"
    assert result["message"] == "为飞羽精灵接入外部大模型也许能获得更好的体验"


def test_species_extraction_uses_structured_local_chat() -> None:
    assistant = StubAssistant(
        [
            chat_response(
                {
                    "order": {
                        "chinese_name": "雀形目",
                        "scientific_name": "Passeriformes",
                        "evidence": "雀形目 Passeriformes",
                    },
                    "family": {
                        "chinese_name": "鸦科",
                        "scientific_name": "Corvidae",
                        "evidence": "鸦科 Corvidae",
                    },
                    "genus": {
                        "chinese_name": "喜鹊属",
                        "scientific_name": "Pica",
                        "evidence": "喜鹊属 Pica",
                    },
                    "species": {
                        "chinese_name": "喜鹊",
                        "scientific_name": "Pica serica",
                        "evidence": "喜鹊 Pica serica",
                    },
                    "subspecies": [],
                    "missing_fields": [],
                    "warnings": [],
                }
            )
        ]
    )

    result = assistant.extract_species("喜鹊 Pica serica")

    assert result.species.chinese_name == "喜鹊"
    assert result.species.scientific_name == "Pica serica"
    path, payload = assistant.requests[0]
    assert path == "/api/chat"
    assert payload is not None
    assert payload["model"] == "feiyu-jingling"
    assert payload["think"] is False
    assert payload["stream"] is False
    assert payload["format"]["type"] == "object"
    assert "只提取原文明示" in payload["messages"][0]["content"]


def test_invalid_model_json_is_reported() -> None:
    assistant = StubAssistant([{"message": {"content": "not json"}}])

    with pytest.raises(FeatherAssistantError) as error:
        assistant.parse_search("查找喜鹊")

    assert error.value.status_code == 502


def test_help_is_grounded_in_local_documentation() -> None:
    assistant = StubAssistant(
        [chat_response({"answer": "点击“登记新发现”。", "suggestions": []})]
    )

    result = assistant.answer_help("observations", "怎样新建观察？")

    assert result.answer == "探险家，我已经翻到对应的档案页了。点击“登记新发现”。"
    _path, payload = assistant.requests[0]
    assert payload is not None
    assert "一笔观察对应一张照片" in payload["messages"][0]["content"]
    assert "不得称为“旅行者”" in payload["messages"][0]["content"]
    assert payload["options"]["temperature"] == 0.25


def test_help_voice_replaces_disallowed_address() -> None:
    assistant = StubAssistant(
        [
            chat_response(
                {
                    "answer": "旅行者，请点击“登记新发现”。",
                    "suggestions": ["旅行者还可以做什么？"],
                }
            )
        ]
    )

    result = assistant.answer_help("observations", "怎样新建观察？")

    assert result.answer == "探险家，请点击“登记新发现”。"
    assert result.suggestions == ["探险家还可以做什么？"]


def test_general_chat_uses_selected_external_provider() -> None:
    assistant = HybridAssistant([])

    result = assistant.answer_chat(
        "home",
        [AssistantChatMessage(role="user", content="我们聊聊鸟类迁徙吧")],
    )

    assert result.answer == "探险家，当然可以聊聊迁徙路线。"
    assert len(assistant.external_requests) == 1
    config, messages, temperature, _max_tokens = assistant.external_requests[0]
    assert config["model"] == "external-model"
    assert messages[-1]["content"] == "我们聊聊鸟类迁徙吧"
    assert "不要输出 JSON" in messages[0]["content"]
    assert temperature == 0.55
    assert result.suggestions == []


def test_observation_query_skill_uses_selected_openai_compatible_provider() -> None:
    assistant = HybridAssistant([])
    assistant._request_openai_chat = lambda *args, **kwargs: json.dumps(
        {
            "interpretation": "查询2024年4月5日的全部记录",
            "sql": (
                "SELECT observation_id FROM field_observations "
                "WHERE observed_date = :observed_date"
            ),
            "parameters": {"observed_date": "2024-04-05"},
            "sort": "desc",
            "warnings": [],
        },
        ensure_ascii=False,
    )

    result = assistant.plan_observation_query("请查询2024年4月5日的全部记录")

    assert result.parameters == {"observed_date": "2024-04-05"}
    assert "field_observations" in result.sql


def test_external_plain_chat_is_truncated_without_validation_failure() -> None:
    result = FeatherAssistant._external_chat_response("羽" * 4000)

    assert len(result.answer) == 3000
    assert result.answer.endswith("……")


def test_structured_extraction_stays_local_when_external_chat_is_selected() -> None:
    assistant = HybridAssistant(
        [
            chat_response(
                {
                    "order": {"chinese_name": None, "scientific_name": None, "evidence": None},
                    "family": {"chinese_name": None, "scientific_name": None, "evidence": None},
                    "genus": {
                        "chinese_name": "喜鹊属",
                        "scientific_name": "Pica",
                        "evidence": "喜鹊属 Pica",
                    },
                    "species": {
                        "chinese_name": "喜鹊",
                        "scientific_name": "Pica serica",
                        "evidence": "喜鹊 Pica serica",
                    },
                    "subspecies": [],
                    "missing_fields": ["order", "family"],
                    "warnings": [],
                }
            )
        ]
    )

    result = assistant.extract_species("喜鹊属 Pica，喜鹊 Pica serica")

    assert result.species.scientific_name == "Pica serica"
    assert len(assistant.requests) == 1
    assert assistant.external_requests == []


def test_taxonomy_research_uses_external_model_but_only_supplied_evidence() -> None:
    assistant = HybridAssistant([])
    assistant._request_openai_chat = lambda config, messages, **kwargs: json.dumps(
        {
            "order": {
                "chinese_name": "雀形目",
                "scientific_name": "Passeriformes",
                "evidence": "Passeriformes",
            },
            "family": {
                "chinese_name": "鹟科",
                "scientific_name": "Muscicapidae",
                "evidence": "Muscicapidae",
            },
            "genus": {
                "chinese_name": None,
                "scientific_name": "Larvivora",
                "evidence": "Larvivora cyane",
            },
            "species": {
                "chinese_name": "蓝歌鸲",
                "scientific_name": "Larvivora cyane",
                "evidence": "蓝歌鸲 Larvivora cyane",
            },
            "subspecies": [],
            "missing_fields": ["subspecies"],
            "warnings": ["资料未提供亚种信息"],
        },
        ensure_ascii=False,
    )

    result = assistant.research_species(
        "蓝歌鸲",
        "[资料 1] 蓝歌鸲 Larvivora cyane；Passeriformes；Muscicapidae。",
    )

    assert result.species.scientific_name == "Larvivora cyane"
    assert result.subspecies == []


def test_knowledge_search_plan_can_expand_chinese_name_for_document_lookup() -> None:
    assistant = HybridAssistant([])
    assistant._request_openai_chat = lambda *args, **kwargs: json.dumps(
        {"query_terms": ["蓝歌鸲", "Siberian Blue Robin", "Larvivora cyane"]},
        ensure_ascii=False,
    )

    result = assistant.plan_knowledge_search("蓝歌鸲")

    assert "Larvivora cyane" in result.query_terms


@pytest.mark.parametrize(
    ("base_url", "expected"),
    [
        ("https://example.com", "https://example.com/v1/chat/completions"),
        ("https://example.com/v1", "https://example.com/v1/chat/completions"),
        ("https://example.com/openai/v1", "https://example.com/openai/v1/chat/completions"),
        ("https://example.com/v1/chat/completions", "https://example.com/v1/chat/completions"),
    ],
)
def test_openai_compatible_endpoint_normalization(base_url, expected) -> None:
    assert FeatherAssistant._chat_completions_url(base_url) == expected


def test_catalog_lookup_normalizes_punctuation_and_reports_ambiguity() -> None:
    items = [
        {"id": 1, "chinese_name": "喜鹊", "scientific_name": "Pica serica"},
        {"id": 2, "chinese_name": "欧亚喜鹊", "scientific_name": "Pica pica"},
    ]

    assert normalized_lookup(" Pica-serica ") == "picaserica"
    match, candidates = resolve_catalog_item(
        "Pica serica", items, ("chinese_name", "scientific_name")
    )
    assert match == items[0]
    assert candidates == []

    match, candidates = resolve_catalog_item(
        "喜鹊", items, ("chinese_name", "scientific_name")
    )
    assert match == items[0]
    assert candidates == []

    match, candidates = resolve_catalog_item(
        "Pica", items, ("chinese_name", "scientific_name")
    )
    assert match is None
    assert candidates == ["喜鹊", "欧亚喜鹊"]


def test_assistant_http_routes_are_wired_without_external_network(tmp_path) -> None:
    assistant = StubAssistant(
        [
            {"models": [{"name": "feiyu-jingling:latest"}]},
            chat_response(
                {
                    "order": {
                        "chinese_name": None,
                        "scientific_name": None,
                        "evidence": None,
                    },
                    "family": {
                        "chinese_name": None,
                        "scientific_name": None,
                        "evidence": None,
                    },
                    "genus": {
                        "chinese_name": "喜鹊属",
                        "scientific_name": "Pica",
                        "evidence": "喜鹊属 Pica",
                    },
                    "species": {
                        "chinese_name": "喜鹊",
                        "scientific_name": "Pica serica",
                        "evidence": "喜鹊 Pica serica",
                    },
                    "subspecies": [],
                    "missing_fields": ["order", "family"],
                    "warnings": [],
                }
            ),
        ]
    )
    app = create_app(Settings(_env_file=None, data_dir=tmp_path / "library"))

    with TestClient(app) as client:
        app.state.feather_assistant = assistant
        status = client.get("/api/assistant/status")
        extraction = client.post(
            "/api/assistant/species-extract",
            json={"text": "喜鹊属 Pica，喜鹊 Pica serica"},
        )

    assert status.status_code == 200
    assert status.json()["available"] is True
    assert extraction.status_code == 200
    assert extraction.json()["species"]["scientific_name"] == "Pica serica"
