from __future__ import annotations

import hashlib
import json
import os
import shutil
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
        filename = f"tsubasa-backup-{stamp}.zip"
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
            archived_files = [("data/database.sqlite", snapshot), *[
                ((Path("data") / path.relative_to(self.settings.data_dir)).as_posix(), path)
                for path in media_files
            ]]
            file_manifest = {
                archive_name: {
                    "size_bytes": path.stat().st_size,
                    "sha256": self._file_sha256(path),
                }
                for archive_name, path in archived_files
            }
            manifest = {
                "format": 2,
                "app": self.settings.app_name,
                "app_version": self.settings.app_version,
                "created_at": created_at.isoformat(timespec="seconds"),
                "database": "data/database.sqlite",
                "media_file_count": len(media_files),
                "files": file_manifest,
            }
            temporary_zip = Path(temporary) / filename
            with zipfile.ZipFile(
                temporary_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
            ) as archive:
                archive.writestr(
                    "manifest.json",
                    json.dumps(manifest, ensure_ascii=False, indent=2),
                )
                for archive_name, path in archived_files:
                    archive.write(path, archive_name)

            temporary_zip.replace(destination)

        return {
            "filename": filename,
            "created_at": manifest["created_at"],
            "size_bytes": destination.stat().st_size,
            "sha256": self._file_sha256(destination),
            "download_url": f"/api/backups/{filename}",
        }

    def restore(self, backup_path: Path) -> dict:
        """Validate a complete backup and replace database/media as one recoverable unit."""
        self.settings.backups_dir.mkdir(parents=True, exist_ok=True)
        safety_backup = self.create()
        with tempfile.TemporaryDirectory(
            dir=self.settings.backups_dir,
            prefix="restore-staging-",
        ) as temporary:
            workspace = Path(temporary)
            staged_data = workspace / "staged" / "data"
            rollback_data = workspace / "rollback"
            staged_data.mkdir(parents=True)
            rollback_data.mkdir(parents=True)
            manifest = self._extract_and_validate(backup_path, staged_data)
            self._swap_restored_data(staged_data, rollback_data)

        return {
            "restored": True,
            "source_filename": backup_path.name,
            "backup_created_at": manifest.get("created_at"),
            "media_file_count": manifest.get("media_file_count", 0),
            "safety_backup": safety_backup,
            "message": "资料库已恢复并通过数据库与媒体校验。",
        }

    def _extract_and_validate(self, backup_path: Path, staged_data: Path) -> dict:
        try:
            archive = zipfile.ZipFile(backup_path)
        except (OSError, zipfile.BadZipFile) as exc:
            raise ValueError("所选文件不是有效的资料库备份") from exc
        with archive:
            members = archive.infolist()
            if len(members) > 100_000:
                raise ValueError("备份包含过多文件")
            if sum(item.file_size for item in members) > 20 * 1024 * 1024 * 1024:
                raise ValueError("备份解压后的大小超过 20 GB 限制")
            names = {item.filename for item in members if not item.is_dir()}
            if "manifest.json" not in names or "data/database.sqlite" not in names:
                raise ValueError("备份缺少 manifest.json 或数据库快照")
            try:
                manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError, KeyError) as exc:
                raise ValueError("备份清单无法读取") from exc
            if manifest.get("app") != self.settings.app_name or manifest.get("format") not in {
                1,
                2,
            }:
                raise ValueError("备份格式或应用标识不受支持")

            allowed_roots = ("data/photos/", "data/thumbnails/", "data/audio/")
            for member in members:
                name = member.filename.replace("\\", "/")
                pure = Path(name)
                if pure.is_absolute() or ".." in pure.parts:
                    raise ValueError("备份包含不安全的文件路径")
                if member.is_dir() or name == "manifest.json":
                    continue
                if name != "data/database.sqlite" and not name.startswith(allowed_roots):
                    raise ValueError(f"备份包含不允许恢复的文件：{name}")
                destination = (staged_data.parent / pure).resolve()
                if not destination.is_relative_to(staged_data.parent.resolve()):
                    raise ValueError("备份文件路径超出恢复目录")
                destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source, destination.open("wb") as target:
                    shutil.copyfileobj(source, target, length=1024 * 1024)

        self._validate_manifest_files(manifest, staged_data)
        self._validate_database_and_media(staged_data)
        self._upgrade_staged_database(staged_data)
        self._validate_database_and_media(staged_data)
        return manifest

    def _upgrade_staged_database(self, staged_data: Path) -> None:
        from .database import Database

        staged_settings = self.settings.model_copy(update={"data_dir": staged_data})
        database = Database(staged_settings)
        try:
            database.create_schema()
        finally:
            database.engine.dispose()

    def _validate_manifest_files(self, manifest: dict, staged_data: Path) -> None:
        if manifest.get("format") != 2:
            return
        files = manifest.get("files")
        if not isinstance(files, dict) or not files:
            raise ValueError("备份缺少文件校验清单")
        for archive_name, expected in files.items():
            if not isinstance(archive_name, str) or not archive_name.startswith("data/"):
                raise ValueError("备份文件校验清单包含无效路径")
            path = staged_data.parent / Path(archive_name)
            if not path.is_file() or not isinstance(expected, dict):
                raise ValueError(f"备份缺少清单中的文件：{archive_name}")
            if path.stat().st_size != expected.get("size_bytes"):
                raise ValueError(f"备份文件大小校验失败：{archive_name}")
            if self._file_sha256(path) != expected.get("sha256"):
                raise ValueError(f"备份文件哈希校验失败：{archive_name}")

    def _validate_database_and_media(self, staged_data: Path) -> None:
        database_path = staged_data / "database.sqlite"
        connection = sqlite3.connect(f"file:{database_path.as_posix()}?mode=ro", uri=True)
        try:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()
            if integrity is None or integrity[0] != "ok":
                raise ValueError("恢复数据库完整性检查失败")
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            required = {
                "alembic_version",
                "collection_plan_slots",
                "collection_plan_species",
                "collection_plan_subitems",
                "collection_plans",
                "media_assets",
                "observations",
                "species",
            }
            if not required.issubset(tables):
                raise ValueError("恢复数据库缺少必要的数据表")
            assets = connection.execute(
                "SELECT relative_path, thumbnail_relative_path, sha256 FROM media_assets"
            ).fetchall()
        finally:
            connection.close()

        for relative_path, thumbnail_path, expected_sha256 in assets:
            media_path = self._safe_media_path(staged_data, relative_path)
            if not media_path.is_file():
                raise ValueError(f"恢复备份缺少媒体文件：{relative_path}")
            if self._file_sha256(media_path) != expected_sha256:
                raise ValueError(f"恢复媒体哈希校验失败：{relative_path}")
            if thumbnail_path:
                thumbnail = self._safe_media_path(staged_data, thumbnail_path)
                if not thumbnail.is_file():
                    raise ValueError(f"恢复备份缺少缩略图：{thumbnail_path}")

    @staticmethod
    def _safe_media_path(data_root: Path, relative_path: str) -> Path:
        path = (data_root / relative_path).resolve()
        if not path.is_relative_to(data_root.resolve()):
            raise ValueError("恢复数据库包含不安全的媒体路径")
        return path

    def _swap_restored_data(self, staged_data: Path, rollback_data: Path) -> None:
        targets = [
            self.settings.database_path,
            self.settings.photos_dir,
            self.settings.thumbnails_dir,
            self.settings.audio_dir,
        ]
        moved_live: list[tuple[Path, Path]] = []
        installed: list[Path] = []
        try:
            sidecars = [
                Path(f"{self.settings.database_path}-wal"),
                Path(f"{self.settings.database_path}-shm"),
            ]
            for live in [*targets, *sidecars]:
                if live.exists():
                    rollback = rollback_data / live.name
                    os.replace(live, rollback)
                    moved_live.append((live, rollback))
            for live in targets:
                staged = staged_data / live.name
                if staged.exists():
                    os.replace(staged, live)
                    installed.append(live)
                elif live != self.settings.database_path:
                    live.mkdir(parents=True, exist_ok=True)
                    installed.append(live)
        except OSError:
            for live in reversed(installed):
                if live.is_dir():
                    shutil.rmtree(live)
                elif live.exists():
                    live.unlink()
            for live, rollback in reversed(moved_live):
                if rollback.exists():
                    os.replace(rollback, live)
            raise

    @staticmethod
    def _file_sha256(path: Path) -> str:
        hasher = hashlib.sha256()
        with path.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                hasher.update(chunk)
        return hasher.hexdigest()

    def resolve(self, filename: str) -> Path:
        if Path(filename).name != filename or not filename.endswith(".zip"):
            raise ValueError("备份文件名无效")
        path = (self.settings.backups_dir / filename).resolve()
        if not path.is_relative_to(self.settings.backups_dir.resolve()) or not path.is_file():
            raise FileNotFoundError(filename)
        return path
