import asyncio
import json
import tempfile
from collections.abc import Generator
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import ValidationError
from sqlalchemy.orm import Session

from .assistant_catalog import normalized_lookup
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
from .export_service import observations_csv
from .feather_assistant import FeatherAssistantError
from .integration_store import IntegrationConfigError
from .map_service import AmapService, MapServiceError
from .media_store import MediaStore, MediaValidationError
from .models import MediaAsset
from .observation_query_skill import ObservationQueryError, ObservationQueryExecutor
from .schemas import (
    LocationInput,
    LocationObservationSelectionInput,
    ObservationInput,
    ObservationSelectionInput,
    ObservationSpeciesInput,
    ObservationUpdateInput,
    SpeciesAudioInput,
    SpeciesProfileUpdateInput,
    TripInput,
    TripObservationSelectionInput,
)
from .services import BirdService, DomainError
from .update_service import UpdateError

router = APIRouter(prefix="/api")


def assistant_error(exc: FeatherAssistantError) -> HTTPException:
    return HTTPException(exc.status_code, exc.message)


def integration_error(exc: IntegrationConfigError) -> HTTPException:
    return HTTPException(422, str(exc))


def assistant_library_context(request: Request, question: str) -> str | None:
    project_terms = (
        "记录",
        "观察",
        "物种",
        "鸟种",
        "馆藏",
        "资料库",
        "地点",
        "区域",
        "远征",
        "多少",
        "几笔",
        "几种",
    )
    if not any(term in question for term in project_terms):
        return None
    query = normalized_lookup(question)
    with request.app.state.database.session_factory() as session:
        service = service_for(request, session)
        stats = service.stats()
        species = service.list_species()
        locations = service.list_locations()
        trips = service.list_trips()

        def matches(item: dict, fields: tuple[str, ...]) -> bool:
            return any(
                (needle := normalized_lookup(str(item.get(field) or ""))) and needle in query
                for field in fields
            )

        matched_species = [
            item
            for item in species
            if matches(item, ("chinese_name", "scientific_name", "catalog_number"))
        ][:3]
        matched_locations = [
            item
            for item in locations
            if matches(item, ("name", "catalog_number", "city", "district"))
        ][:3]
        matched_trips = [
            item for item in trips if matches(item, ("name", "catalog_number"))
        ][:3]
        include_records = any(term in question for term in ("哪些", "列出", "分别", "时间", "日期"))
        species_context = []
        for item in matched_species:
            entry = {
                "catalog_number": item["catalog_number"],
                "chinese_name": item["chinese_name"],
                "scientific_name": item["scientific_name"],
                "observation_count": item["observation_count"],
            }
            if include_records:
                detail = service.species_detail(item["id"])
                entry["records"] = [
                    {
                        "id": record["id"],
                        "observed_at": record["observed_at"],
                        "admin1_name": record["admin1_name"],
                        "locality": record["locality"],
                    }
                    for record in detail["observations"][:20]
                ]
            species_context.append(entry)
        context = {
            "source": "翼·时光记当前数据库的只读即时摘要",
            "totals": stats,
            "matched_species": species_context,
            "matched_locations": [
                {
                    "catalog_number": item["catalog_number"],
                    "name": item["name"],
                    "observation_count": item["observation_count"],
                    "species_count": item["species_count"],
                    "trip_count": item["trip_count"],
                }
                for item in matched_locations
            ],
            "matched_trips": [
                {
                    "catalog_number": item["catalog_number"],
                    "name": item["name"],
                    "observation_count": item["observation_count"],
                    "species_count": item["species_count"],
                    "location_count": item["location_count"],
                }
                for item in matched_trips
            ],
        }
    return json.dumps(context, ensure_ascii=False, separators=(",", ":"))


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


def get_session(request: Request) -> Generator[Session, None, None]:
    yield from request.app.state.database.session()


def service_for(request: Request, session: Session) -> BirdService:
    return BirdService(session, request.app.state.media_store)


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
        library_context = await asyncio.to_thread(
            assistant_library_context,
            request,
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


@router.get("/stats")
def stats(request: Request) -> dict:
    with request.app.state.database.session_factory() as session:
        return service_for(request, session).stats()


@router.get("/species")
def list_species(request: Request) -> list[dict]:
    with request.app.state.database.session_factory() as session:
        return service_for(request, session).list_species()


@router.get("/taxonomy/tree")
def taxonomy_tree(request: Request) -> list[dict]:
    with request.app.state.database.session_factory() as session:
        return service_for(request, session).taxonomy_tree()


@router.get("/species/{species_id}")
def species_detail(species_id: int, request: Request) -> dict:
    with request.app.state.database.session_factory() as session:
        try:
            return service_for(request, session).species_detail(species_id)
        except DomainError as exc:
            raise HTTPException(exc.status_code, exc.message) from exc


@router.put("/species/{species_id}/profile")
def update_species_profile(
    species_id: int,
    payload: SpeciesProfileUpdateInput,
    request: Request,
) -> dict:
    with request.app.state.database.session_factory() as session:
        try:
            return service_for(request, session).update_species_profile(species_id, payload)
        except DomainError as exc:
            raise HTTPException(exc.status_code, exc.message) from exc


@router.get("/observations")
def list_observations(request: Request) -> list[dict]:
    with request.app.state.database.session_factory() as session:
        return service_for(request, session).list_observations()


@router.get("/exports/observations.csv", response_class=Response)
def export_observations_csv(request: Request) -> Response:
    with request.app.state.database.session_factory() as session:
        content = observations_csv(service_for(request, session).list_observations())
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="tsubasa-observations.csv"'},
    )


@router.get("/home/cover")
def homepage_cover(request: Request) -> dict:
    with request.app.state.database.session_factory() as session:
        return service_for(request, session).homepage_feature()


@router.put("/home/cover")
def set_homepage_cover(
    payload: ObservationSelectionInput,
    request: Request,
) -> dict:
    with request.app.state.database.session_factory() as session:
        try:
            return service_for(request, session).set_homepage_feature(
                payload.observation_id
            )
        except DomainError as exc:
            raise HTTPException(exc.status_code, exc.message) from exc


@router.get("/locations")
def list_locations(request: Request) -> list[dict]:
    with request.app.state.database.session_factory() as session:
        return service_for(request, session).list_locations()


@router.post("/locations", status_code=201)
def create_location(payload: LocationInput, request: Request) -> dict:
    with request.app.state.database.session_factory() as session:
        try:
            return service_for(request, session).create_location(payload)
        except DomainError as exc:
            raise HTTPException(exc.status_code, exc.message) from exc


@router.get("/locations/{location_id}")
def location_detail(location_id: int, request: Request) -> dict:
    with request.app.state.database.session_factory() as session:
        try:
            return service_for(request, session).location_detail(location_id)
        except DomainError as exc:
            raise HTTPException(exc.status_code, exc.message) from exc


@router.post("/locations/{location_id}/cover")
async def set_location_cover(
    location_id: int,
    request: Request,
    photo: UploadFile = File(...),
) -> dict:
    with request.app.state.database.session_factory() as session:
        try:
            return await service_for(request, session).set_location_cover(location_id, photo)
        except DomainError as exc:
            raise HTTPException(exc.status_code, exc.message) from exc
        except MediaValidationError as exc:
            raise HTTPException(422, str(exc)) from exc


@router.put("/locations/{location_id}")
def update_location(location_id: int, payload: LocationInput, request: Request) -> dict:
    with request.app.state.database.session_factory() as session:
        try:
            return service_for(request, session).update_location(location_id, payload)
        except DomainError as exc:
            raise HTTPException(exc.status_code, exc.message) from exc


@router.put("/locations/{location_id}/observations")
def set_location_observations(
    location_id: int,
    payload: LocationObservationSelectionInput,
    request: Request,
) -> dict:
    with request.app.state.database.session_factory() as session:
        try:
            return service_for(request, session).set_location_observations(location_id, payload)
        except DomainError as exc:
            raise HTTPException(exc.status_code, exc.message) from exc


@router.delete("/locations/{location_id}")
def delete_location(location_id: int, request: Request) -> dict:
    with request.app.state.database.session_factory() as session:
        try:
            return service_for(request, session).delete_location(location_id)
        except DomainError as exc:
            raise HTTPException(exc.status_code, exc.message) from exc


@router.get("/trips")
def list_trips(request: Request) -> list[dict]:
    with request.app.state.database.session_factory() as session:
        return service_for(request, session).list_trips()


@router.post("/trips", status_code=201)
def create_trip(payload: TripInput, request: Request) -> dict:
    with request.app.state.database.session_factory() as session:
        try:
            return service_for(request, session).create_trip(payload)
        except DomainError as exc:
            raise HTTPException(exc.status_code, exc.message) from exc


@router.get("/trips/{trip_id}")
def trip_detail(trip_id: int, request: Request) -> dict:
    with request.app.state.database.session_factory() as session:
        try:
            return service_for(request, session).trip_detail(trip_id)
        except DomainError as exc:
            raise HTTPException(exc.status_code, exc.message) from exc


@router.put("/trips/{trip_id}")
def update_trip(trip_id: int, payload: TripInput, request: Request) -> dict:
    with request.app.state.database.session_factory() as session:
        try:
            return service_for(request, session).update_trip(trip_id, payload)
        except DomainError as exc:
            raise HTTPException(exc.status_code, exc.message) from exc


@router.put("/trips/{trip_id}/observations")
def set_trip_observations(
    trip_id: int,
    payload: TripObservationSelectionInput,
    request: Request,
) -> dict:
    with request.app.state.database.session_factory() as session:
        try:
            return service_for(request, session).set_trip_observations(trip_id, payload)
        except DomainError as exc:
            raise HTTPException(exc.status_code, exc.message) from exc


@router.put("/trips/{trip_id}/cover")
def set_trip_cover(
    trip_id: int,
    payload: ObservationSelectionInput,
    request: Request,
) -> dict:
    with request.app.state.database.session_factory() as session:
        try:
            return service_for(request, session).set_trip_cover(
                trip_id, payload.observation_id
            )
        except DomainError as exc:
            raise HTTPException(exc.status_code, exc.message) from exc


@router.delete("/trips/{trip_id}")
def delete_trip(trip_id: int, request: Request) -> dict:
    with request.app.state.database.session_factory() as session:
        try:
            return service_for(request, session).delete_trip(trip_id)
        except DomainError as exc:
            raise HTTPException(exc.status_code, exc.message) from exc


@router.post("/media/exif-time")
def read_exif_time(request: Request, photo: UploadFile = File(...)) -> dict:
    try:
        captured_at, source = request.app.state.media_store.read_photo_datetime(photo)
        return {
            "observed_at": (
                captured_at.isoformat(timespec="minutes") if captured_at is not None else None
            ),
            "source": source,
        }
    except MediaValidationError as exc:
        raise HTTPException(422, str(exc)) from exc
    finally:
        photo.file.close()


@router.put("/species/{species_id}/cover")
def set_species_cover(
    species_id: int,
    payload: ObservationSelectionInput,
    request: Request,
) -> dict:
    with request.app.state.database.session_factory() as session:
        try:
            return service_for(request, session).set_species_cover(
                species_id, payload.observation_id
            )
        except DomainError as exc:
            raise HTTPException(exc.status_code, exc.message) from exc


@router.post("/observations", status_code=201)
async def create_observation(
    request: Request,
    payload: str = Form(...),
    photo: UploadFile = File(...),
    audio: list[UploadFile] | None = File(default=None),
) -> dict:
    try:
        metadata = ObservationInput.model_validate_json(payload)
    except ValidationError as exc:
        raise HTTPException(422, exc.errors(include_context=False)) from exc

    with request.app.state.database.session_factory() as session:
        try:
            result = await service_for(request, session).create_observation(metadata, photo, audio)
            return {
                "observation_id": result.observation.id,
                "species_id": result.species.id,
                "catalog_number": result.species.catalog_number,
                "species_entries": [
                    {
                        "id": entry.id,
                        "species_id": entry.species_id,
                        "catalog_number": entry.species.catalog_number,
                        "is_primary": entry.is_primary,
                    }
                    for entry in result.observation.species_entries
                ],
            }
        except DomainError as exc:
            raise HTTPException(exc.status_code, exc.message) from exc
        except MediaValidationError as exc:
            raise HTTPException(422, str(exc)) from exc


@router.patch("/observations/{observation_id}")
def update_observation(
    observation_id: int,
    payload: ObservationUpdateInput,
    request: Request,
) -> dict:
    with request.app.state.database.session_factory() as session:
        try:
            return service_for(request, session).update_observation(observation_id, payload)
        except DomainError as exc:
            raise HTTPException(exc.status_code, exc.message) from exc


@router.patch("/observations/{observation_id}/species/{entry_id}")
def update_observation_species(
    observation_id: int,
    entry_id: int,
    payload: ObservationUpdateInput,
    request: Request,
) -> dict:
    with request.app.state.database.session_factory() as session:
        try:
            return service_for(request, session).update_observation_species(
                observation_id, entry_id, payload
            )
        except DomainError as exc:
            raise HTTPException(exc.status_code, exc.message) from exc


@router.post("/observations/{observation_id}/species", status_code=201)
def add_observation_species(
    observation_id: int,
    payload: ObservationSpeciesInput,
    request: Request,
) -> dict:
    with request.app.state.database.session_factory() as session:
        try:
            return service_for(request, session).add_observation_species(
                observation_id, payload
            )
        except DomainError as exc:
            raise HTTPException(exc.status_code, exc.message) from exc


@router.delete("/observations/{observation_id}/species/{entry_id}")
def delete_observation_species(
    observation_id: int,
    entry_id: int,
    request: Request,
) -> dict:
    with request.app.state.database.session_factory() as session:
        try:
            return service_for(request, session).delete_observation_species(
                observation_id, entry_id
            )
        except DomainError as exc:
            raise HTTPException(exc.status_code, exc.message) from exc


@router.delete("/observations/{observation_id}")
def delete_observation(observation_id: int, request: Request) -> dict:
    with request.app.state.database.session_factory() as session:
        try:
            return service_for(request, session).delete_observation(observation_id)
        except DomainError as exc:
            raise HTTPException(exc.status_code, exc.message) from exc


@router.post("/species/{species_id}/audio", status_code=201)
async def add_species_audio(
    species_id: int,
    request: Request,
    audio: UploadFile = File(...),
    payload: str = Form(default="{}"),
) -> dict:
    try:
        metadata = SpeciesAudioInput.model_validate_json(payload)
    except ValidationError as exc:
        raise HTTPException(422, exc.errors(include_context=False)) from exc
    with request.app.state.database.session_factory() as session:
        try:
            link = await service_for(request, session).add_species_audio(
                species_id, metadata, audio
            )
            return {"id": link.id, "asset_id": link.asset_id}
        except DomainError as exc:
            raise HTTPException(exc.status_code, exc.message) from exc
        except MediaValidationError as exc:
            raise HTTPException(422, str(exc)) from exc


@router.delete("/species/{species_id}/audio/{audio_id}")
def delete_species_audio(species_id: int, audio_id: int, request: Request) -> dict:
    with request.app.state.database.session_factory() as session:
        try:
            return service_for(request, session).delete_species_audio(species_id, audio_id)
        except DomainError as exc:
            raise HTTPException(exc.status_code, exc.message) from exc


@router.get("/media/{asset_id}", response_class=FileResponse)
def get_media(asset_id: int, request: Request, thumbnail: bool = False) -> FileResponse:
    with request.app.state.database.session_factory() as session:
        asset = session.get(MediaAsset, asset_id)
        if asset is None:
            raise HTTPException(404, "媒体文件不存在")
        store: MediaStore = request.app.state.media_store
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
