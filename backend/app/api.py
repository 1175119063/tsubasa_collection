import asyncio
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse

from .assistant_context_service import AssistantLibraryContextService
from .assistant_schemas import (
    AmapIntegrationInput,
    AssistantChatInput,
    AssistantHelpInput,
    AssistantSearchInput,
    AssistantTaxonomyResearchInput,
    AssistantTaxonomyResearchResponse,
    AssistantTextInput,
    LlmIntegrationInput,
)
from .database import Database
from .feather_assistant import FeatherAssistantError
from .integration_store import IntegrationConfigError
from .map_service import AmapService, MapServiceError
from .observation_query_skill import ObservationQueryError, ObservationQueryExecutor
from .routes.catalog import router as catalog_router
from .routes.collections import router as collection_router
from .routes.locations import router as location_router
from .routes.media import router as media_router
from .routes.observations import router as observation_router
from .routes.trips import router as trip_router
from .update_service import UpdateError

router = APIRouter(prefix="/api")


def assistant_error(exc: FeatherAssistantError) -> HTTPException:
    return HTTPException(exc.status_code, exc.message)


def integration_error(exc: IntegrationConfigError) -> HTTPException:
    return HTTPException(422, str(exc))


@router.post("/backups", status_code=201)
def create_backup(request: Request) -> dict:
    try:
        return request.app.state.backup_service.create()
    except (OSError, RuntimeError) as exc:
        raise HTTPException(500, f"创建备份失败：{exc}") from exc


@router.get("/backups/{filename}", response_class=FileResponse)
def download_backup(filename: str, request: Request) -> FileResponse:
    try:
        path = request.app.state.backup_service.resolve(filename)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(404, "备份文件不存在") from exc
    return FileResponse(path, media_type="application/zip", filename=filename)


@router.post("/backups/restore")
async def restore_backup(request: Request, backup: UploadFile = File(...)) -> dict:
    if not backup.filename or not backup.filename.lower().endswith(".zip"):
        raise HTTPException(422, "请选择翼·时光记生成的 ZIP 备份")
    temporary_path: Path | None = None
    database_disposed = False
    try:
        request.app.state.settings.backups_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            dir=request.app.state.settings.backups_dir,
            prefix="restore-upload-",
            suffix=".zip",
            delete=False,
        ) as target:
            temporary_path = Path(target.name)
            total = 0
            while chunk := await backup.read(1024 * 1024):
                total += len(chunk)
                if total > 20 * 1024 * 1024 * 1024:
                    raise HTTPException(413, "备份文件超过 20 GB 限制")
                target.write(chunk)

        request.app.state.database.engine.dispose()
        database_disposed = True
        result = await asyncio.to_thread(
            request.app.state.backup_service.restore,
            temporary_path,
        )
    except HTTPException:
        raise
    except (OSError, RuntimeError, ValueError) as exc:
        raise HTTPException(422, f"恢复备份失败：{exc}") from exc
    finally:
        await backup.close()
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        if database_disposed:
            database = Database(request.app.state.settings)
            database.create_schema()
            request.app.state.database = database
    return result


@router.get("/health")
def health(request: Request) -> dict:
    return {
        "status": "ok",
        "app": request.app.state.settings.app_name,
        "version": request.app.state.settings.app_version,
    }


@router.get("/updates/status")
def update_status(request: Request) -> dict:
    try:
        return request.app.state.update_service.check()
    except UpdateError as exc:
        raise HTTPException(502, str(exc)) from exc


@router.post("/updates/download")
def download_update(request: Request) -> dict:
    try:
        return request.app.state.update_service.download()
    except UpdateError as exc:
        raise HTTPException(502, str(exc)) from exc


@router.get("/updates/files/{filename}", response_class=FileResponse)
def get_update_file(filename: str, request: Request) -> FileResponse:
    try:
        path = request.app.state.update_service.resolve(filename)
    except FileNotFoundError as exc:
        raise HTTPException(404, "更新安装包不存在") from exc
    return FileResponse(path, media_type="application/vnd.microsoft.portable-executable")


@router.get("/assistant/status")
async def feather_assistant_status(request: Request) -> dict:
    return await asyncio.to_thread(request.app.state.feather_assistant.status)


@router.post("/assistant/species-extract")
async def feather_assistant_extract_species(
    payload: AssistantTextInput,
    request: Request,
) -> dict:
    try:
        result = await asyncio.to_thread(
            request.app.state.feather_assistant.extract_species,
            payload.text,
        )
    except FeatherAssistantError as exc:
        raise assistant_error(exc) from exc
    return result.model_dump()


@router.get("/assistant/knowledge")
def feather_assistant_knowledge(request: Request) -> dict:
    return request.app.state.knowledge_library.summary()


@router.post("/assistant/taxonomy-research")
async def feather_assistant_taxonomy_research(
    payload: AssistantTaxonomyResearchInput,
    request: Request,
) -> dict:
    try:
        passages = await asyncio.to_thread(
            request.app.state.knowledge_library.search,
            payload.query,
        )
    except RuntimeError as exc:
        raise HTTPException(422, str(exc)) from exc
    if not passages:
        try:
            plan = await asyncio.to_thread(
                request.app.state.feather_assistant.plan_knowledge_search,
                payload.query,
            )
        except FeatherAssistantError as exc:
            raise assistant_error(exc) from exc
        collected = {}
        for term in plan.query_terms:
            for item in await asyncio.to_thread(
                request.app.state.knowledge_library.search,
                term,
            ):
                collected[(item.source_id, item.locator)] = item
        passages = sorted(
            collected.values(),
            key=lambda item: (-item.score, item.title, item.locator),
        )[:6]
    if not passages:
        raise HTTPException(404, "本地资料中没有找到相关证据，请补充资料或换一个名称。")
    evidence = "\n\n".join(
        f"[资料 {index}｜{item.title}｜{item.locator}]\n{item.excerpt}"
        for index, item in enumerate(passages, start=1)
    )
    try:
        extraction = await asyncio.to_thread(
            request.app.state.feather_assistant.research_species,
            payload.query,
            evidence,
        )
    except FeatherAssistantError as exc:
        raise assistant_error(exc) from exc
    response = AssistantTaxonomyResearchResponse(
        query=payload.query,
        extraction=extraction,
        citations=[
            {
                "source_id": item.source_id,
                "title": item.title,
                "locator": item.locator,
                "excerpt": item.excerpt,
            }
            for item in passages
        ],
    )
    return response.model_dump()


@router.post("/assistant/search-parse")
async def feather_assistant_parse_search(
    payload: AssistantSearchInput,
    request: Request,
) -> dict:
    try:
        plan = await asyncio.to_thread(
            request.app.state.feather_assistant.plan_observation_query,
            payload.query,
        )
        execution = await asyncio.to_thread(
            ObservationQueryExecutor(request.app.state.settings.database_path).execute,
            plan,
        )
    except FeatherAssistantError as exc:
        raise assistant_error(exc) from exc
    except ObservationQueryError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    count = len(execution.observation_ids)
    qualifier = "至少" if execution.truncated else ""
    answer = (
        f"找到{qualifier}{count}笔符合条件的田野记录，已在页面中展示。"
        if count
        else "没有找到符合这些条件的田野记录。"
    )
    return {
        "interpretation": plan.interpretation,
        "observation_ids": execution.observation_ids,
        "result_count": count,
        "truncated": execution.truncated,
        "sort": plan.sort,
        "warnings": plan.warnings,
        "answer": answer,
    }


@router.post("/assistant/help")
async def feather_assistant_help(payload: AssistantHelpInput, request: Request) -> dict:
    try:
        result = await asyncio.to_thread(
            request.app.state.feather_assistant.answer_help,
            payload.page,
            payload.question,
        )
    except FeatherAssistantError as exc:
        raise assistant_error(exc) from exc
    return result.model_dump()


@router.post("/assistant/chat")
async def feather_assistant_chat(payload: AssistantChatInput, request: Request) -> dict:
    try:
        context_service = AssistantLibraryContextService(
            request.app.state.database,
            request.app.state.media_store,
        )
        library_context = await asyncio.to_thread(
            context_service.build,
            payload.messages[-1].content,
        )
        result = await asyncio.to_thread(
            request.app.state.feather_assistant.answer_chat,
            payload.page,
            payload.messages,
            library_context,
        )
    except FeatherAssistantError as exc:
        raise assistant_error(exc) from exc
    return result.model_dump()


@router.get("/integrations")
def integration_summary(request: Request) -> dict:
    try:
        result = request.app.state.integration_store.summary()
    except IntegrationConfigError as exc:
        raise integration_error(exc) from exc
    settings = request.app.state.settings
    result["local_model"] = {
        "base_url": settings.feather_assistant_base_url,
        "model": settings.feather_assistant_model,
    }
    return result


@router.put("/integrations/amap")
def update_amap_integration(payload: AmapIntegrationInput, request: Request) -> dict:
    try:
        return request.app.state.integration_store.update_amap(
            payload.api_key,
            payload.clear_api_key,
        )
    except IntegrationConfigError as exc:
        raise integration_error(exc) from exc


@router.post("/integrations/amap/test")
def test_amap_integration(request: Request) -> dict:
    try:
        items = AmapService(request.app.state.integration_store.get_amap_key()).search(
            "北京市"
        )
    except (IntegrationConfigError, MapServiceError) as exc:
        status_code = exc.status_code if isinstance(exc, MapServiceError) else 422
        raise HTTPException(status_code, str(exc)) from exc
    return {"ok": True, "result_count": len(items), "message": "高德地图 API 连接成功。"}


@router.put("/integrations/llm")
def update_llm_integration(payload: LlmIntegrationInput, request: Request) -> dict:
    try:
        return request.app.state.integration_store.update_llm(
            payload.provider,
            payload.base_url,
            payload.model,
            payload.api_key,
            payload.clear_api_key,
        )
    except IntegrationConfigError as exc:
        raise integration_error(exc) from exc


@router.post("/integrations/llm/test")
async def test_llm_integration(request: Request) -> dict:
    try:
        return await asyncio.to_thread(
            request.app.state.feather_assistant.test_external_connection
        )
    except FeatherAssistantError as exc:
        raise assistant_error(exc) from exc


@router.get("/map/config")
def map_config(request: Request) -> dict:
    try:
        key = request.app.state.integration_store.get_amap_key()
    except IntegrationConfigError as exc:
        raise integration_error(exc) from exc
    return {
        "provider": "amap",
        "map_provider": "openstreetmap",
        "enabled": bool(key),
    }


@router.get("/map/search")
def search_map_places(
    request: Request,
    query: str = Query(min_length=1, max_length=120),
    city: str | None = Query(default=None, max_length=80),
) -> dict:
    try:
        return {
            "items": AmapService(request.app.state.integration_store.get_amap_key()).search(
                query, city
            )
        }
    except (IntegrationConfigError, MapServiceError) as exc:
        status_code = exc.status_code if isinstance(exc, MapServiceError) else 422
        raise HTTPException(status_code, str(exc)) from exc


@router.get("/map/reverse")
def reverse_map_point(
    request: Request,
    latitude: float = Query(ge=-90, le=90),
    longitude: float = Query(ge=-180, le=180),
) -> dict:
    try:
        return AmapService(request.app.state.integration_store.get_amap_key()).reverse_wgs84(
            latitude, longitude
        )
    except (IntegrationConfigError, MapServiceError) as exc:
        status_code = exc.status_code if isinstance(exc, MapServiceError) else 422
        raise HTTPException(status_code, str(exc)) from exc


domain_routers = (
    catalog_router,
    observation_router,
    location_router,
    trip_router,
    collection_router,
    media_router,
)
