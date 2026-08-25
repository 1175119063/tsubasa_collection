from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from .config import Settings


class UpdateError(RuntimeError):
    pass


class UpdateService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def check(self) -> dict:
        if not self.settings.update_manifest_url:
            return {
                "configured": False,
                "update_available": False,
                "current_version": self.settings.app_version,
                "message": "当前发行版尚未配置更新清单地址。",
            }
        manifest_url = self._https_url(self.settings.update_manifest_url, "更新清单")
        manifest = self._request_json(manifest_url)
        parsed = self._parse_manifest(manifest)
        available = self._version_tuple(parsed["version"]) > self._version_tuple(
            self.settings.app_version
        )
        return {
            "configured": True,
            "update_available": available,
            "current_version": self.settings.app_version,
            **parsed,
            "message": (
                f"发现新版本 {parsed['version']}。"
                if available
                else "当前已经是最新版本。"
            ),
        }

    def download(self) -> dict:
        status = self.check()
        if not status.get("update_available"):
            raise UpdateError(status["message"])
        self.settings.updates_dir.mkdir(parents=True, exist_ok=True)
        filename = f"yuhen-update-v{status['version']}.exe"
        destination = self.settings.updates_dir / filename
        temporary = self.settings.updates_dir / f".{filename}.download"
        request = Request(status["installer_url"], headers={"User-Agent": "Yuhen-Updater/1"})
        hasher = hashlib.sha256()
        total = 0
        try:
            with urlopen(request, timeout=60) as response, temporary.open("wb") as target:  # noqa: S310
                while chunk := response.read(1024 * 1024):
                    total += len(chunk)
                    if total > 1024 * 1024 * 1024:
                        raise UpdateError("更新安装包超过 1 GB 限制")
                    hasher.update(chunk)
                    target.write(chunk)
            if hasher.hexdigest().casefold() != status["sha256"].casefold():
                raise UpdateError("更新安装包 SHA-256 校验失败")
            temporary.replace(destination)
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise UpdateError("无法下载更新安装包") from exc
        finally:
            temporary.unlink(missing_ok=True)
        return {
            "filename": filename,
            "version": status["version"],
            "size_bytes": destination.stat().st_size,
            "sha256": status["sha256"],
            "download_url": f"/api/updates/files/{filename}",
            "message": (
                "更新安装包已下载并通过 SHA-256 校验。"
                "请先完整备份，再关闭软件并运行安装包。"
            ),
        }

    def resolve(self, filename: str) -> Path:
        if Path(filename).name != filename or not filename.endswith(".exe"):
            raise FileNotFoundError(filename)
        path = (self.settings.updates_dir / filename).resolve()
        if not path.is_relative_to(self.settings.updates_dir.resolve()) or not path.is_file():
            raise FileNotFoundError(filename)
        return path

    def _parse_manifest(self, manifest: dict) -> dict:
        try:
            version = str(manifest["version"])
            installer_url = self._https_url(str(manifest["installer_url"]), "安装包")
            sha256 = str(manifest["sha256"]).casefold()
        except (KeyError, TypeError, ValueError) as exc:
            raise UpdateError("更新清单字段无效") from exc
        self._version_tuple(version)
        if not re.fullmatch(r"[0-9a-f]{64}", sha256):
            raise UpdateError("更新清单中的 SHA-256 无效")
        return {
            "version": version,
            "installer_url": installer_url,
            "sha256": sha256,
            "notes": str(manifest.get("notes") or ""),
        }

    @staticmethod
    def _version_tuple(version: str) -> tuple[int, int, int]:
        if not re.fullmatch(r"\d+\.\d+\.\d+", version):
            raise UpdateError("版本号必须使用 major.minor.patch 格式")
        return tuple(int(part) for part in version.split("."))  # type: ignore[return-value]

    @staticmethod
    def _https_url(value: str, label: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise UpdateError(f"{label}地址必须是无账号信息的 HTTPS URL")
        return value

    @staticmethod
    def _request_json(url: str) -> dict:
        try:
            request = Request(url, headers={"User-Agent": "Yuhen-Updater/1"})
            with urlopen(request, timeout=15) as response:  # noqa: S310
                content = response.read(1024 * 1024 + 1)
            if len(content) > 1024 * 1024:
                raise UpdateError("更新清单超过 1 MB 限制")
            value = json.loads(content.decode("utf-8"))
            if not isinstance(value, dict):
                raise UpdateError("更新清单必须是 JSON 对象")
            return value
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise UpdateError("无法读取更新清单") from exc
