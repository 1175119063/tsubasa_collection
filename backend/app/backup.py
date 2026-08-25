from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from .config import Settings


class BackupService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def create(self) -> dict:
        created_at = datetime.now().astimezone()
        stamp = created_at.strftime("%Y%m%d-%H%M%S-%f")
        filename = f"yuhen-backup-{stamp}.zip"
        destination = self.settings.backups_dir / filename
        self.settings.backups_dir.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(dir=self.settings.backups_dir) as temporary:
            snapshot = Path(temporary) / "database.sqlite"
            source_connection = sqlite3.connect(self.settings.database_path)
            target_connection = sqlite3.connect(snapshot)
            try:
                source_connection.backup(target_connection)
                result = target_connection.execute("PRAGMA integrity_check").fetchone()
                if result is None or result[0] != "ok":
                    raise RuntimeError("备份数据库完整性检查失败")
            finally:
                target_connection.close()
                source_connection.close()

            media_files = [
                path
                for directory in (
                    self.settings.photos_dir,
                    self.settings.thumbnails_dir,
                    self.settings.audio_dir,
                )
                for path in directory.rglob("*")
                if path.is_file()
            ]
            manifest = {
                "format": 1,
                "app": self.settings.app_name,
                "app_version": self.settings.app_version,
                "created_at": created_at.isoformat(timespec="seconds"),
                "database": "data/database.sqlite",
                "media_file_count": len(media_files),
            }
            temporary_zip = Path(temporary) / filename
            with zipfile.ZipFile(
                temporary_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
            ) as archive:
                archive.write(snapshot, "data/database.sqlite")
                archive.writestr(
                    "manifest.json",
                    json.dumps(manifest, ensure_ascii=False, indent=2),
                )
                for path in media_files:
                    archive.write(path, (Path("data") / path.relative_to(self.settings.data_dir)))

            temporary_zip.replace(destination)

        hasher = hashlib.sha256()
        with destination.open("rb") as backup_file:
            while chunk := backup_file.read(1024 * 1024):
                hasher.update(chunk)
        return {
            "filename": filename,
            "created_at": manifest["created_at"],
            "size_bytes": destination.stat().st_size,
            "sha256": hasher.hexdigest(),
            "download_url": f"/api/backups/{filename}",
        }

    def resolve(self, filename: str) -> Path:
        if Path(filename).name != filename or not filename.endswith(".zip"):
            raise ValueError("备份文件名无效")
        path = (self.settings.backups_dir / filename).resolve()
        if not path.is_relative_to(self.settings.backups_dir.resolve()) or not path.is_file():
            raise FileNotFoundError(filename)
        return path
