from __future__ import annotations

import pytest
from app.assistant_schemas import LlmIntegrationInput
from app.config import Settings
from app.integration_store import IntegrationConfigError, IntegrationStore
from app.main import create_app
from fastapi.testclient import TestClient
from pydantic import ValidationError


class XorProtector:
    def protect(self, value: bytes) -> bytes:
        return bytes(item ^ 0xA5 for item in value)

    def unprotect(self, value: bytes) -> bytes:
        return self.protect(value)


def settings(tmp_path, amap_key: str | None = None) -> Settings:
    return Settings(
        _env_file=None,
        data_dir=tmp_path / "library",
        amap_web_service_key=amap_key,
    )


def test_managed_keys_are_encrypted_and_masked(tmp_path) -> None:
    store = IntegrationStore(settings(tmp_path), XorProtector())

    summary = store.update_amap("amap-secret-1234", False)
    summary = store.update_llm(
        "openai_compatible",
        "https://example.com/v1",
        "example-model",
        "llm-secret-5678",
        False,
    )

    raw = store.path.read_bytes()
    assert b"amap-secret" not in raw
    assert b"llm-secret" not in raw
    assert summary["amap"]["key_hint"] == "••••••••1234"
    assert summary["llm"]["api_key_hint"] == "••••••••5678"

    reloaded = IntegrationStore(settings(tmp_path), XorProtector())
    assert reloaded.get_amap_key() == "amap-secret-1234"
    assert reloaded.get_llm()["api_key"] == "llm-secret-5678"


def test_environment_amap_key_can_be_replaced_and_cleared(tmp_path) -> None:
    store = IntegrationStore(settings(tmp_path, "environment-key"), XorProtector())

    assert store.summary()["amap"]["source"] == "environment"
    store.update_amap("managed-key", False)
    assert store.get_amap_key() == "managed-key"
    store.update_amap(None, True)
    assert store.get_amap_key() is None
    assert store.summary()["amap"]["configured"] is False


def test_external_provider_requires_complete_configuration(tmp_path) -> None:
    store = IntegrationStore(settings(tmp_path), XorProtector())

    with pytest.raises(IntegrationConfigError):
        store.update_llm(
            "openai_compatible",
            "https://example.com/v1",
            "example-model",
            None,
            False,
        )


@pytest.mark.parametrize(
    "url",
    [
        "example.com/v1",
        "http://example.com/v1",
        "https://user:password@example.com/v1",
        "https://example.com/v1?debug=1",
    ],
)
def test_remote_base_url_validation_rejects_unsafe_values(url) -> None:
    with pytest.raises(ValidationError):
        LlmIntegrationInput(
            provider="openai_compatible",
            base_url=url,
            model="model",
            api_key="secret",
        )


def test_local_http_base_url_is_allowed() -> None:
    value = LlmIntegrationInput(
        provider="openai_compatible",
        base_url="http://127.0.0.1:8001/v1",
        model="model",
        api_key="secret",
    )

    assert value.base_url == "http://127.0.0.1:8001/v1"


def test_integration_management_routes_do_not_return_plaintext_keys(tmp_path) -> None:
    app_settings = settings(tmp_path, "environment-key")
    app = create_app(app_settings)
    store = IntegrationStore(app_settings, XorProtector())

    with TestClient(app) as client:
        app.state.integration_store = store
        summary = client.get("/api/integrations")
        updated = client.put(
            "/api/integrations/amap",
            json={"api_key": "managed-key-4321", "clear_api_key": False},
        )
        local = client.put(
            "/api/integrations/llm",
            json={
                "provider": "local",
                "base_url": None,
                "model": None,
                "api_key": None,
                "clear_api_key": False,
            },
        )

    assert summary.status_code == 200
    assert summary.json()["local_model"]["model"] == "feiyu-jingling"
    assert updated.status_code == 200
    assert updated.json()["amap"]["key_hint"] == "••••••••4321"
    assert "managed-key" not in updated.text
    assert local.status_code == 200
