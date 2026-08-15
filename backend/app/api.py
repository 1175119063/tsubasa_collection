from collections.abc import Generator

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from .media_store import MediaStore, MediaValidationError
from .models import MediaAsset
from .schemas import (
    LocationInput,
    LocationObservationSelectionInput,
    ObservationInput,
    ObservationSelectionInput,
    ObservationUpdateInput,
    SpeciesAudioInput,
    TripInput,
    TripObservationSelectionInput,
)
from .services import BirdService, DomainError

router = APIRouter(prefix="/api")


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


@router.get("/observations")
def list_observations(request: Request) -> list[dict]:
    with request.app.state.database.session_factory() as session:
        return service_for(request, session).list_observations()


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
        return FileResponse(path, media_type=asset.mime_type)
