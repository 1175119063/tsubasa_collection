from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api import router
from .config import Settings
from .database import Database
from .media_store import MediaStore

STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        database = Database(app_settings)
        database.create_schema()
        app.state.settings = app_settings
        app.state.database = database
        app.state.media_store = MediaStore(app_settings)
        yield
        database.engine.dispose()

    app = FastAPI(
        title="羽迹 API",
        version=app_settings.app_version,
        lifespan=lifespan,
    )
    app.include_router(router)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def home_page() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/observations", include_in_schema=False)
    def observations_page() -> FileResponse:
        return FileResponse(STATIC_DIR / "observations.html")

    @app.get("/dex", include_in_schema=False)
    def dex_page() -> FileResponse:
        return FileResponse(STATIC_DIR / "dex.html")

    @app.get("/locations", include_in_schema=False)
    def locations_page() -> FileResponse:
        return FileResponse(STATIC_DIR / "locations.html")

    @app.get("/trips", include_in_schema=False)
    def trips_page() -> FileResponse:
        return FileResponse(STATIC_DIR / "trips.html")

    return app


app = create_app()
