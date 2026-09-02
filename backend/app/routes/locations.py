from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile

from ..api_dependencies import BirdServiceDependency
from ..media_store import MediaValidationError
from ..schemas import LocationInput, LocationObservationSelectionInput

router = APIRouter()


@router.get("/locations")
def list_locations(service: BirdServiceDependency) -> list[dict]:
    return service.list_locations()


@router.post("/locations", status_code=201)
def create_location(payload: LocationInput, service: BirdServiceDependency) -> dict:
    return service.create_location(payload)


@router.get("/locations/{location_id}")
def location_detail(location_id: int, service: BirdServiceDependency) -> dict:
    return service.location_detail(location_id)


@router.post("/locations/{location_id}/cover")
async def set_location_cover(
    location_id: int,
    service: BirdServiceDependency,
    photo: Annotated[UploadFile, File()],
) -> dict:
    try:
        return await service.set_location_cover(location_id, photo)
    except MediaValidationError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.put("/locations/{location_id}")
def update_location(
    location_id: int,
    payload: LocationInput,
    service: BirdServiceDependency,
) -> dict:
    return service.update_location(location_id, payload)


@router.put("/locations/{location_id}/observations")
def set_location_observations(
    location_id: int,
    payload: LocationObservationSelectionInput,
    service: BirdServiceDependency,
) -> dict:
    return service.set_location_observations(location_id, payload)


@router.delete("/locations/{location_id}")
def delete_location(location_id: int, service: BirdServiceDependency) -> dict:
    return service.delete_location(location_id)
