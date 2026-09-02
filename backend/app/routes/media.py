from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from ..api_dependencies import MediaStoreDependency, SessionDependency
from ..media_store import MediaValidationError
from ..models import MediaAsset

router = APIRouter()


@router.post("/media/exif-time")
def read_exif_time(
    store: MediaStoreDependency,
    photo: Annotated[UploadFile, File()],
) -> dict:
    try:
        captured_at, source = store.read_photo_datetime(photo)
        return {
            "observed_at": (
                captured_at.isoformat(timespec="minutes")
                if captured_at is not None
                else None
            ),
            "source": source,
        }
    except MediaValidationError as exc:
        raise HTTPException(422, str(exc)) from exc
    finally:
        photo.file.close()


@router.get("/media/{asset_id}", response_class=FileResponse)
def get_media(
    asset_id: int,
    session: SessionDependency,
    store: MediaStoreDependency,
    thumbnail: bool = False,
) -> FileResponse:
    asset = session.get(MediaAsset, asset_id)
    if asset is None:
        raise HTTPException(404, "媒体文件不存在")
    try:
        path = store.resolve_asset_path(asset, thumbnail=thumbnail)
    except MediaValidationError as exc:
        raise HTTPException(500, str(exc)) from exc
    if not path.is_file():
        raise HTTPException(404, "媒体文件已丢失")
    return FileResponse(
        path,
        media_type=asset.mime_type,
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
        },
    )
