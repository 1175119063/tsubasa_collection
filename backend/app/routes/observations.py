from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import ValidationError

from ..api_dependencies import BirdServiceDependency
from ..export_service import observations_csv
from ..media_store import MediaValidationError
from ..schemas import (
    ObservationInput,
    ObservationPhotoAddInput,
    ObservationPhotoUpdateInput,
    ObservationSpeciesInput,
    ObservationUpdateInput,
)

router = APIRouter()


@router.get("/observations")
def list_observations(service: BirdServiceDependency) -> list[dict]:
    return service.list_observations()


@router.get("/exports/observations.csv", response_class=Response)
def export_observations_csv(service: BirdServiceDependency) -> Response:
    return Response(
        content=observations_csv(service.list_observations()),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="tsubasa-observations.csv"'
        },
    )


@router.post("/observations", status_code=201)
async def create_observation(
    service: BirdServiceDependency,
    payload: Annotated[str, Form()],
    photo: Annotated[UploadFile, File()],
    additional_photos: Annotated[list[UploadFile] | None, File()] = None,
    audio: Annotated[list[UploadFile] | None, File()] = None,
) -> dict:
    try:
        metadata = ObservationInput.model_validate_json(payload)
    except ValidationError as exc:
        raise HTTPException(422, exc.errors(include_context=False)) from exc
    try:
        result = await service.create_observation(metadata, photo, audio, additional_photos)
    except MediaValidationError as exc:
        raise HTTPException(422, str(exc)) from exc
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


@router.post("/observations/{observation_id}/photos", status_code=201)
async def add_observation_photo(
    observation_id: int,
    service: BirdServiceDependency,
    payload: Annotated[str, Form()],
    photo: Annotated[UploadFile, File()],
) -> dict:
    try:
        metadata = ObservationPhotoAddInput.model_validate_json(payload)
    except ValidationError as exc:
        raise HTTPException(422, exc.errors(include_context=False)) from exc
    try:
        return await service.add_observation_photo(observation_id, metadata, photo)
    except MediaValidationError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.patch("/observations/{observation_id}/photos/{photo_id}")
def update_observation_photo(
    observation_id: int,
    photo_id: int,
    payload: ObservationPhotoUpdateInput,
    service: BirdServiceDependency,
) -> dict:
    return service.update_observation_photo(observation_id, photo_id, payload)


@router.delete("/observations/{observation_id}/photos/{photo_id}")
def delete_observation_photo(
    observation_id: int,
    photo_id: int,
    service: BirdServiceDependency,
) -> dict:
    return service.delete_observation_photo(observation_id, photo_id)


@router.patch("/observations/{observation_id}")
def update_observation(
    observation_id: int,
    payload: ObservationUpdateInput,
    service: BirdServiceDependency,
) -> dict:
    return service.update_observation(observation_id, payload)


@router.patch("/observations/{observation_id}/species/{entry_id}")
def update_observation_species(
    observation_id: int,
    entry_id: int,
    payload: ObservationUpdateInput,
    service: BirdServiceDependency,
) -> dict:
    return service.update_observation_species(observation_id, entry_id, payload)


@router.post("/observations/{observation_id}/species", status_code=201)
def add_observation_species(
    observation_id: int,
    payload: ObservationSpeciesInput,
    service: BirdServiceDependency,
) -> dict:
    return service.add_observation_species(observation_id, payload)


@router.delete("/observations/{observation_id}/species/{entry_id}")
def delete_observation_species(
    observation_id: int,
    entry_id: int,
    service: BirdServiceDependency,
) -> dict:
    return service.delete_observation_species(observation_id, entry_id)


@router.delete("/observations/{observation_id}")
def delete_observation(
    observation_id: int,
    service: BirdServiceDependency,
) -> dict:
    return service.delete_observation(observation_id)
