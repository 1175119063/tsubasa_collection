from __future__ import annotations

from collections.abc import Generator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from .media_store import MediaStore
from .services import BirdService


def get_session(request: Request) -> Generator[Session, None, None]:
    """Provide one request-scoped database session and always close it."""
    yield from request.app.state.database.session()


SessionDependency = Annotated[Session, Depends(get_session)]


def get_bird_service(request: Request, session: SessionDependency) -> BirdService:
    return BirdService(session, request.app.state.media_store)


def get_media_store(request: Request) -> MediaStore:
    return request.app.state.media_store


BirdServiceDependency = Annotated[BirdService, Depends(get_bird_service)]
MediaStoreDependency = Annotated[MediaStore, Depends(get_media_store)]
