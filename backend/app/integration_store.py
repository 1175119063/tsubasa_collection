from __future__ import annotations

import ctypes
import json
import os
import threading
from copy import deepcopy
from ctypes import wintypes
from typing import Protocol

from .config import Settings

FILE_HEADER = b"TSUBASA-INTEGRATIONS-V1\0"
LEGACY_FILE_HEADER = bytes.fromhex(
    "59 55 48 45 4e 2d 49 4e 54 45 47 52 41 54 49 4f 4e 53 2d 56 31 00"
)
CRYPTPROTECT_UI_FORBIDDEN = 0x1
CRYPTPROTECT_LOCAL_MACHINE = 0x4


class IntegrationConfigError(RuntimeError):
    pass


class SecretProtector(Protocol):
    def protect(self, value: bytes) -> bytes: ...

    def unprotect(self, value: bytes) -> bytes: ...


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
    ]


class WindowsDpapiProtector:
    description = "翼·时光记 API 配置"

    def __init__(self) -> None:
        if os.name != "nt":
            raise IntegrationConfigError("当前系统不支持 Windows DPAPI，无法安全保存 API Key。")
        self.crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self.crypt32.CryptProtectData.argtypes = [
            ctypes.POINTER(_DataBlob),
            ctypes.c_wchar_p,
            ctypes.POINTER(_DataBlob),
            ctypes.c_void_p,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(_DataBlob),
        ]
        self.crypt32.CryptProtectData.restype = wintypes.BOOL
        self.crypt32.CryptUnprotectData.argtypes = [
            ctypes.POINTER(_DataBlob),
            ctypes.POINTER(ctypes.c_wchar_p),
            ctypes.POINTER(_DataBlob),
            ctypes.c_void_p,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(_DataBlob),
        ]
        self.crypt32.CryptUnprotectData.restype = wintypes.BOOL
        self.kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        self.kernel32.LocalFree.restype = ctypes.c_void_p

    @staticmethod
    def _blob(value: bytes) -> tuple[_DataBlob, ctypes.Array]:
        buffer = ctypes.create_string_buffer(value)
        pointer = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))
        return _DataBlob(len(value), pointer), buffer

    def protect(self, value: bytes) -> bytes:
        source, source_buffer = self._blob(value)
        description = ctypes.c_wchar_p(self.description)
        last_error = 0
        for flags in (
            CRYPTPROTECT_UI_FORBIDDEN,
            CRYPTPROTECT_UI_FORBIDDEN | CRYPTPROTECT_LOCAL_MACHINE,
        ):
            destination = _DataBlob()
            ctypes.set_last_error(0)
            result = self.crypt32.CryptProtectData(
                ctypes.byref(source),
                description,
                None,
                None,
                None,
                flags,
                ctypes.byref(destination),
            )
            if result:
                try:
                    return ctypes.string_at(destination.pbData, destination.cbData)
                finally:
                    self.kernel32.LocalFree(destination.pbData)
            last_error = ctypes.get_last_error()
        del source_buffer
        raise IntegrationConfigError(f"Windows 无法加密 API 配置（错误 {last_error}）。")

    def unprotect(self, value: bytes) -> bytes:
        source, source_buffer = self._blob(value)
        destination = _DataBlob()
        result = self.crypt32.CryptUnprotectData(
            ctypes.byref(source),
            None,
            None,
            None,
            None,
            CRYPTPROTECT_UI_FORBIDDEN,
            ctypes.byref(destination),
        )
        del source_buffer
        if not result:
            error_code = ctypes.get_last_error()
            raise IntegrationConfigError(
                "API 配置无法解密；若资料来自另一台电脑，请重新填写 API Key"
                f"（错误 {error_code}）。"
            )
        try:
            return ctypes.string_at(destination.pbData, destination.cbData)
        finally:
            self.kernel32.LocalFree(destination.pbData)


def _defaults() -> dict:
    return {
        "version": 1,
        "amap": {"api_key": None, "use_environment": True},
        "llm": {
            "provider": "local",
            "base_url": None,
            "api_key": None,
            "model": None,
        },
    }


class IntegrationStore:
    def __init__(
        self,
        settings: Settings,
        protector: SecretProtector | None = None,
    ) -> None:
        self.settings = settings
        self.path = settings.integrations_path
        self.protector = protector
        self._lock = threading.RLock()

    def _get_protector(self) -> SecretProtector:
        if self.protector is None:
            self.protector = WindowsDpapiProtector()
        return self.protector

    def _read(self) -> dict:
        with self._lock:
            if not self.path.is_file():
                return _defaults()
            try:
                encrypted = self.path.read_bytes()
                header = next(
                    (
                        candidate
                        for candidate in (FILE_HEADER, LEGACY_FILE_HEADER)
                        if encrypted.startswith(candidate)
                    ),
                    None,
                )
                if header is None:
                    raise IntegrationConfigError("API 配置文件格式无法识别。")
                plain = self._get_protector().unprotect(encrypted[len(header) :])
                payload = json.loads(plain.decode("utf-8"))
            except IntegrationConfigError:
                raise
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise IntegrationConfigError("API 配置文件已经损坏，无法读取。") from exc
            defaults = _defaults()
            for section in ("amap", "llm"):
                if isinstance(payload.get(section), dict):
                    defaults[section].update(payload[section])
            return defaults

    def _write(self, payload: dict) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(
                "utf-8"
            )
            protected = FILE_HEADER + self._get_protector().protect(encoded)
            temporary = self.path.with_suffix(".tmp")
            try:
                temporary.write_bytes(protected)
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

    def get_llm(self) -> dict:
        return deepcopy(self._read()["llm"])

    def summary(self) -> dict:
        payload = self._read()
        amap = payload["amap"]
        amap_key = self.get_amap_key()
        amap_source = "environment" if amap.get("use_environment", True) and amap_key else "managed"
        llm = payload["llm"]
        return {
            "storage": "windows_dpapi",
            "amap": {
                "configured": bool(amap_key),
                "key_hint": self._masked(amap_key),
                "source": amap_source if amap_key else None,
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
