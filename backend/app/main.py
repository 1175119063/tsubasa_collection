import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api import router
from .backup import BackupService
from .config import Settings
from .database import Database
from .feather_assistant import FeatherAssistant
from .integration_store import IntegrationStore
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
        app.state.backup_service = BackupService(app_settings)
        app.state.integration_store = IntegrationStore(app_settings)
        app.state.feather_assistant = FeatherAssistant(
            app_settings,
            app.state.integration_store,
        )
        app.state.write_lock = asyncio.Lock()
        yield
        database.engine.dispose()

    app = FastAPI(
        title="羽迹 API",
        version=app_settings.app_version,
        lifespan=lifespan,
    )
    @app.middleware("http")
    async def prevent_stale_frontend_assets(request: Request, call_next):
        is_write = (
            request.url.path.startswith("/api/")
            and not request.url.path.startswith("/api/assistant/")
            and request.method in {
            "POST",
            "PUT",
            "PATCH",
            "DELETE",
            }
        )
        if is_write:
            async with request.app.state.write_lock:
                response = await call_next(request)
        else:
            response = await call_next(request)
        content_type = response.headers.get("content-type", "")
        if request.url.path.startswith("/static/") or content_type.startswith("text/html"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

    app.include_router(router)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def home_page() -> FileResponse:
        return FileResponse(STATIC_DIR / "v2-index.html")

    @app.get("/observations", include_in_schema=False)
    def observations_page() -> FileResponse:
        return FileResponse(STATIC_DIR / "v2-observations.html")

    @app.get("/dex", include_in_schema=False)
    def dex_page() -> FileResponse:
        return FileResponse(STATIC_DIR / "v2-dex.html")

    @app.get("/locations", include_in_schema=False)
    def locations_page() -> FileResponse:
        return FileResponse(STATIC_DIR / "v2-locations.html")

    @app.get("/trips", include_in_schema=False)
    def trips_page() -> FileResponse:
        return FileResponse(STATIC_DIR / "v2-trips.html")

    @app.get("/preview", include_in_schema=False)
    def preview_home_page() -> FileResponse:
        return FileResponse(STATIC_DIR / "v2-index.html")

    @app.get("/preview/dex", include_in_schema=False)
    def preview_dex_page() -> FileResponse:
        return FileResponse(STATIC_DIR / "v2-dex.html")

    @app.get("/preview/observations", include_in_schema=False)
    def preview_observations_page() -> FileResponse:
        return FileResponse(STATIC_DIR / "v2-observations.html")

    @app.get("/preview/locations", include_in_schema=False)
    def preview_locations_page() -> FileResponse:
        return FileResponse(STATIC_DIR / "v2-locations.html")

    @app.get("/preview/trips", include_in_schema=False)
    def preview_trips_page() -> FileResponse:
        return FileResponse(STATIC_DIR / "v2-trips.html")

    @app.get("/legacy", include_in_schema=False)
    def legacy_home_page() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/legacy/observations", include_in_schema=False)
    def legacy_observations_page() -> FileResponse:
        return FileResponse(STATIC_DIR / "observations.html")

    @app.get("/legacy/dex", include_in_schema=False)
    def legacy_dex_page() -> FileResponse:
        return FileResponse(STATIC_DIR / "dex.html")

    @app.get("/legacy/locations", include_in_schema=False)
    def legacy_locations_page() -> FileResponse:
        return FileResponse(STATIC_DIR / "locations.html")

    @app.get("/legacy/trips", include_in_schema=False)
    def legacy_trips_page() -> FileResponse:
        return FileResponse(STATIC_DIR / "trips.html")

    return app


app = create_app()
