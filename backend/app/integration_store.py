from __future__ import annotations

import json
import os
import threading
from copy import deepcopy

from .config import Settings

FILE_HEADER = b"TSUBASA-INTEGRATIONS-V2\0"


class IntegrationConfigError(RuntimeError):
    pass


def _defaults() -> dict:
    return {
        "version": 1,
        "amap": {"api_key": None, "use_environment": True},
        "tianditu": {"api_key": None, "use_environment": True},
        "llm": {
            "provider": "local",
            "base_url": None,
            "api_key": None,
            "model": None,
        },
    }


class IntegrationStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.path = settings.integrations_path
        self._lock = threading.RLock()

    def _read(self) -> dict:
        with self._lock:
            if not self.path.is_file():
                return _defaults()
            try:
                content = self.path.read_bytes()
                if not content.startswith(FILE_HEADER):
                    raise IntegrationConfigError("API 配置文件格式无法识别。")
                plain = content[len(FILE_HEADER) :]
                payload = json.loads(plain.decode("utf-8"))
                if not isinstance(payload, dict):
                    raise IntegrationConfigError("API 配置文件格式无法识别。")
            except IntegrationConfigError:
                raise
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise IntegrationConfigError("API 配置文件已经损坏，无法读取。") from exc
            defaults = _defaults()
            for section in ("amap", "tianditu", "llm"):
                if isinstance(payload.get(section), dict):
                    defaults[section].update(payload[section])
            return defaults

    def _write(self, payload: dict) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(
                "utf-8"
            )
            portable = FILE_HEADER + encoded
            temporary = self.path.with_suffix(".tmp")
            try:
                temporary.write_bytes(portable)
                if os.name != "nt":
                    temporary.chmod(0o600)
                temporary.replace(self.path)
            except OSError as exc:
                raise IntegrationConfigError("无法保存 API 配置。") from exc
            finally:
                temporary.unlink(missing_ok=True)

    @staticmethod
    def _masked(value: str | None) -> str | None:
        if not value:
            return None
        suffix = value[-4:] if len(value) >= 4 else value[-1:]
        return f"••••••••{suffix}"

    def get_amap_key(self) -> str | None:
        config = self._read()["amap"]
        if config.get("use_environment", True):
            return self.settings.amap_web_service_key
        return config.get("api_key") or None

    def get_tianditu_key(self) -> str | None:
        config = self._read()["tianditu"]
        if config.get("use_environment", True):
            return self.settings.tianditu_browser_key
        return config.get("api_key") or None

    def get_llm(self) -> dict:
        return deepcopy(self._read()["llm"])

    def summary(self) -> dict:
        payload = self._read()
        amap = payload["amap"]
        amap_key = self.get_amap_key()
        amap_source = "environment" if amap.get("use_environment", True) and amap_key else "managed"
        tianditu = payload["tianditu"]
        tianditu_key = self.get_tianditu_key()
        tianditu_source = (
            "environment"
            if tianditu.get("use_environment", True) and tianditu_key
            else "managed"
        )
        llm = payload["llm"]
        return {
            "storage": "portable_local_file",
            "amap": {
                "configured": bool(amap_key),
                "key_hint": self._masked(amap_key),
                "source": amap_source if amap_key else None,
            },
            "tianditu": {
                "configured": bool(tianditu_key),
                "key_hint": self._masked(tianditu_key),
                "source": tianditu_source if tianditu_key else None,
            },
            "llm": {
                "provider": llm.get("provider") or "local",
                "base_url": llm.get("base_url"),
                "model": llm.get("model"),
                "api_key_configured": bool(llm.get("api_key")),
                "api_key_hint": self._masked(llm.get("api_key")),
            },
        }

    def update_amap(self, api_key: str | None, clear_api_key: bool) -> dict:
        payload = self._read()
        if clear_api_key:
            payload["amap"] = {"api_key": None, "use_environment": False}
        elif api_key:
            payload["amap"] = {"api_key": api_key.strip(), "use_environment": False}
        self._write(payload)
        return self.summary()

    def update_tianditu(self, api_key: str | None, clear_api_key: bool) -> dict:
        payload = self._read()
        if clear_api_key:
            payload["tianditu"] = {"api_key": None, "use_environment": False}
        elif api_key:
            payload["tianditu"] = {"api_key": api_key.strip(), "use_environment": False}
        self._write(payload)
        return self.summary()

    def update_llm(
        self,
        provider: str,
        base_url: str | None,
        model: str | None,
        api_key: str | None,
        clear_api_key: bool,
    ) -> dict:
        payload = self._read()
        current_key = payload["llm"].get("api_key")
        if clear_api_key:
            current_key = None
        elif api_key:
            current_key = api_key.strip()
        payload["llm"] = {
            "provider": provider,
            "base_url": base_url.rstrip("/") if base_url else None,
            "model": model.strip() if model else None,
            "api_key": current_key,
        }
        if provider == "openai_compatible" and not all(
            (payload["llm"]["base_url"], payload["llm"]["model"], current_key)
        ):
            raise IntegrationConfigError(
                "启用外部大模型前，必须填写 Base URL、模型名称和 API Key。"
            )
        self._write(payload)
        return self.summary()
