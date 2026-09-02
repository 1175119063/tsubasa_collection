from __future__ import annotations

from fastapi import APIRouter

from ..api_dependencies import BirdServiceDependency
from ..schemas import ObservationSelectionInput, TripInput, TripObservationSelectionInput

router = APIRouter()


@router.get("/trips")
def list_trips(service: BirdServiceDependency) -> list[dict]:
    return service.list_trips()


@router.post("/trips", status_code=201)
def create_trip(payload: TripInput, service: BirdServiceDependency) -> dict:
    return service.create_trip(payload)


@router.get("/trips/{trip_id}")
def trip_detail(trip_id: int, service: BirdServiceDependency) -> dict:
    return service.trip_detail(trip_id)


@router.put("/trips/{trip_id}")
def update_trip(
    trip_id: int,
    payload: TripInput,
    service: BirdServiceDependency,
) -> dict:
    return service.update_trip(trip_id, payload)


@router.put("/trips/{trip_id}/observations")
def set_trip_observations(
    trip_id: int,
    payload: TripObservationSelectionInput,
    service: BirdServiceDependency,
) -> dict:
    return service.set_trip_observations(trip_id, payload)


@router.put("/trips/{trip_id}/cover")
def set_trip_cover(
    trip_id: int,
    payload: ObservationSelectionInput,
    service: BirdServiceDependency,
) -> dict:
    return service.set_trip_cover(trip_id, payload.observation_id)


@router.delete("/trips/{trip_id}")
def delete_trip(trip_id: int, service: BirdServiceDependency) -> dict:
    return service.delete_trip(trip_id)
