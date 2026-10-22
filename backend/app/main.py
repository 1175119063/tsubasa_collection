import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from .api import domain_routers, router
from .backup import BackupService
from .config import Settings
from .database import Database
from .feather_assistant import FeatherAssistant
from .integration_store import IntegrationStore
from .knowledge_service import KnowledgeLibrary
from .media_store import MediaStore
from .service_common import DomainError
from .update_service import UpdateService

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
        app.state.update_service = UpdateService(app_settings)
        app.state.integration_store = IntegrationStore(app_settings)
        app.state.knowledge_library = KnowledgeLibrary(app_settings.knowledge_dir)
        app.state.knowledge_library.ensure_directories()
        app.state.feather_assistant = FeatherAssistant(
            app_settings,
            app.state.integration_store,
        )
        app.state.write_lock = asyncio.Lock()
        yield
        database.engine.dispose()

    app = FastAPI(
        title="翼·时光记 API",
        version=app_settings.app_version,
        lifespan=lifespan,
    )

    @app.exception_handler(DomainError)
    async def domain_error_response(_request: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message},
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
    for domain_router in domain_routers:
        app.include_router(domain_router, prefix="/api")
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    @app.get("/observations", include_in_schema=False)
    @app.get("/dex", include_in_schema=False)
    @app.get("/locations", include_in_schema=False)
    @app.get("/map", include_in_schema=False)
    @app.get("/trips", include_in_schema=False)
    @app.get("/collections", include_in_schema=False)
    def frontend_app_page() -> FileResponse:
        """Serve the Vue application on every public frontend route."""
        return FileResponse(STATIC_DIR / "vue" / "index.html")

    @app.get("/vue", include_in_schema=False)
    @app.get("/vue/{frontend_path:path}", include_in_schema=False)
    @app.get("/preview", include_in_schema=False)
    @app.get("/preview/{frontend_path:path}", include_in_schema=False)
    @app.get("/legacy", include_in_schema=False)
    @app.get("/legacy/{frontend_path:path}", include_in_schema=False)
    def retired_frontend_redirect(
        request: Request, frontend_path: str = ""
    ) -> RedirectResponse:
        """Keep old bookmarks useful without retaining either retired frontend."""
        target = f"/{frontend_path.lstrip('/')}" if frontend_path else "/"
        if request.url.query:
            target = f"{target}?{request.url.query}"
        return RedirectResponse(target, status_code=308)

    return app


app = create_app()
