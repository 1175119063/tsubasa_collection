from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from mutagen.mp3 import MP3, HeaderNotFoundError
from PIL import ExifTags, Image, ImageOps, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import Settings
from .enums import MediaKind
from .models import MediaAsset

PHOTO_MAX_BYTES = 10 * 1024 * 1024


class MediaValidationError(ValueError):
    pass


@dataclass
class ImportedMedia:
    asset: MediaAsset
    created_files: list[Path]


class MediaStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def read_photo_datetime(self, upload: UploadFile) -> tuple[datetime | None, str | None]:
        suffix = Path(upload.filename or "").suffix.casefold()
        if suffix not in {".jpg", ".jpeg"}:
            raise MediaValidationError("照片仅支持 JPEG/JPG")
        try:
            upload.file.seek(0, os.SEEK_END)
            if upload.file.tell() > PHOTO_MAX_BYTES:
                raise MediaValidationError("照片大小不能超过 10 MB")
            upload.file.seek(0)
            with Image.open(upload.file) as image:
                if image.format != "JPEG":
                    raise MediaValidationError("文件内容不是有效 JPEG")
                exif = image.getexif()
                exif_ifd = {}
                try:
                    exif_ifd = exif.get_ifd(ExifTags.IFD.Exif)
                except (AttributeError, KeyError, TypeError):
                    pass
                candidates = (
                    (exif_ifd.get(36867) or exif.get(36867), "DateTimeOriginal"),
                    (exif_ifd.get(36868) or exif.get(36868), "DateTimeDigitized"),
                    (exif.get(306), "DateTime"),
                )
                for raw_value, source in candidates:
                    captured_at = self._parse_exif_datetime(raw_value)
                    if captured_at is not None:
                        return captured_at.replace(second=0, microsecond=0), source
                return None, None
        except (UnidentifiedImageError, OSError) as exc:
            raise MediaValidationError("JPEG 文件损坏或无法读取") from exc
        finally:
            upload.file.seek(0)

    @staticmethod
    def _parse_exif_datetime(raw_value: object) -> datetime | None:
        if isinstance(raw_value, bytes):
            raw_value = raw_value.decode("ascii", errors="ignore")
        if not isinstance(raw_value, str):
            return None
        value = raw_value.strip().strip("\x00")
        for date_format in ("%Y:%m:%d %H:%M:%S", "%Y:%m:%d %H:%M"):
            try:
                return datetime.strptime(value, date_format)
            except ValueError:
                continue
        return None

    async def import_photo(self, session: Session, upload: UploadFile) -> ImportedMedia:
        suffix = Path(upload.filename or "").suffix.casefold()
        if suffix not in {".jpg", ".jpeg"}:
            raise MediaValidationError("照片仅支持 JPEG/JPG")

        temp_path, sha256, byte_size = await self._copy_to_temp(
            upload,
            max_bytes=PHOTO_MAX_BYTES,
            too_large_message="照片大小不能超过 10 MB",
        )
        created_files: list[Path] = []
        try:
            try:
                with Image.open(temp_path) as image:
                    if image.format != "JPEG":
                        raise MediaValidationError("文件内容不是有效 JPEG")
                    image.verify()
                with Image.open(temp_path) as image:
                    oriented = ImageOps.exif_transpose(image)
                    width, height = oriented.size
                    thumbnail = oriented.copy()
                    thumbnail.thumbnail((720, 720))
            except (UnidentifiedImageError, OSError) as exc:
                raise MediaValidationError("JPEG 文件损坏或无法读取") from exc

            existing = session.scalar(select(MediaAsset).where(MediaAsset.sha256 == sha256))
            if existing is not None:
                if existing.kind is not MediaKind.PHOTO:
                    raise MediaValidationError("相同文件已作为其他媒体类型存在")
                temp_path.unlink(missing_ok=True)
                return ImportedMedia(existing, [])

            relative_path = Path("photos") / sha256[:2] / f"{sha256}.jpg"
            thumbnail_relative_path = Path("thumbnails") / sha256[:2] / f"{sha256}.jpg"
            destination = self.settings.data_dir / relative_path
            thumbnail_destination = self.settings.data_dir / thumbnail_relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            thumbnail_destination.parent.mkdir(parents=True, exist_ok=True)
            os.replace(temp_path, destination)
            created_files.append(destination)
            thumbnail.save(thumbnail_destination, format="JPEG", quality=86, optimize=True)
            created_files.append(thumbnail_destination)

            asset = MediaAsset(
                kind=MediaKind.PHOTO,
                sha256=sha256,
                relative_path=relative_path.as_posix(),
                thumbnail_relative_path=thumbnail_relative_path.as_posix(),
                original_filename=Path(upload.filename or "photo.jpg").name,
                mime_type="image/jpeg",
                byte_size=byte_size,
                width=width,
                height=height,
            )
            session.add(asset)
            session.flush()
            return ImportedMedia(asset, created_files)
        except Exception:
            temp_path.unlink(missing_ok=True)
            for path in created_files:
                path.unlink(missing_ok=True)
            raise

    async def import_audio(self, session: Session, upload: UploadFile) -> ImportedMedia:
        suffix = Path(upload.filename or "").suffix.casefold()
        if suffix != ".mp3":
            raise MediaValidationError("录音仅支持 MP3")

        temp_path, sha256, byte_size = await self._copy_to_temp(upload)
        created_files: list[Path] = []
        try:
            try:
                audio = MP3(temp_path)
                duration_seconds = float(audio.info.length)
            except (HeaderNotFoundError, OSError) as exc:
                raise MediaValidationError("MP3 文件损坏或无法读取") from exc

            existing = session.scalar(select(MediaAsset).where(MediaAsset.sha256 == sha256))
            if existing is not None:
                if existing.kind is not MediaKind.AUDIO:
                    raise MediaValidationError("相同文件已作为其他媒体类型存在")
                temp_path.unlink(missing_ok=True)
                return ImportedMedia(existing, [])

            relative_path = Path("audio") / sha256[:2] / f"{sha256}.mp3"
            destination = self.settings.data_dir / relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            os.replace(temp_path, destination)
            created_files.append(destination)

            asset = MediaAsset(
                kind=MediaKind.AUDIO,
                sha256=sha256,
                relative_path=relative_path.as_posix(),
                original_filename=Path(upload.filename or "audio.mp3").name,
                mime_type="audio/mpeg",
                byte_size=byte_size,
                duration_seconds=duration_seconds,
            )
            session.add(asset)
            session.flush()
            return ImportedMedia(asset, created_files)
        except Exception:
            temp_path.unlink(missing_ok=True)
            for path in created_files:
                path.unlink(missing_ok=True)
            raise

    async def _copy_to_temp(
        self,
        upload: UploadFile,
        *,
        max_bytes: int | None = None,
        too_large_message: str = "上传文件过大",
    ) -> tuple[Path, str, int]:
        temp_path = self.settings.temp_dir / f"{uuid4().hex}.upload"
        hasher = hashlib.sha256()
        byte_size = 0
        try:
            with temp_path.open("wb") as destination:
                while chunk := await upload.read(1024 * 1024):
                    if max_bytes is not None and byte_size + len(chunk) > max_bytes:
                        raise MediaValidationError(too_large_message)
                    destination.write(chunk)
                    hasher.update(chunk)
                    byte_size += len(chunk)
            if byte_size == 0:
                raise MediaValidationError("上传文件为空")
            return temp_path, hasher.hexdigest(), byte_size
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise
        finally:
            await upload.close()

    def resolve_asset_path(self, asset: MediaAsset, *, thumbnail: bool = False) -> Path:
        relative = asset.thumbnail_relative_path if thumbnail else asset.relative_path
        if relative is None:
            relative = asset.relative_path
        candidate = (self.settings.data_dir / relative).resolve()
        data_root = self.settings.data_dir.resolve()
        if not candidate.is_relative_to(data_root):
            raise MediaValidationError("媒体路径越过资料库边界")
        return candidate

    def remove_files(self, asset: MediaAsset) -> None:
        for relative in (asset.relative_path, asset.thumbnail_relative_path):
            if relative:
                path = (self.settings.data_dir / relative).resolve()
                if path.is_relative_to(self.settings.data_dir.resolve()):
                    path.unlink(missing_ok=True)
