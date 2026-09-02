from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..api_dependencies import BirdServiceDependency
from ..media_store import MediaValidationError
from ..schemas import (
    CollectionLogoInput,
    CollectionPlanInput,
    CollectionPlanSpeciesInput,
    CollectionSlotEvidenceInput,
    CollectionSpeciesIntroductionInput,
)

router = APIRouter()


@router.get("/collections")
def list_collection_plans(service: BirdServiceDependency) -> list[dict]:
    return service.list_collection_plans()


@router.post("/collections", status_code=201)
def create_collection_plan(
    payload: CollectionPlanInput,
    service: BirdServiceDependency,
) -> dict:
    return service.create_collection_plan(payload)


@router.get("/collections/{plan_id}")
def collection_plan_detail(plan_id: int, service: BirdServiceDependency) -> dict:
    return service.collection_plan_detail(plan_id)


@router.put("/collections/{plan_id}")
def update_collection_plan(
    plan_id: int,
    payload: CollectionPlanInput,
    service: BirdServiceDependency,
) -> dict:
    return service.update_collection_plan(plan_id, payload)


@router.delete("/collections/{plan_id}")
def delete_collection_plan(plan_id: int, service: BirdServiceDependency) -> dict:
    return service.delete_collection_plan(plan_id)


@router.put("/collections/{plan_id}/species")
def set_collection_plan_species(
    plan_id: int,
    payload: CollectionPlanSpeciesInput,
    service: BirdServiceDependency,
) -> dict:
    return service.set_collection_plan_species(plan_id, payload)


@router.put("/collections/{plan_id}/logo")
def set_collection_plan_logo(
    plan_id: int,
    payload: CollectionLogoInput,
    service: BirdServiceDependency,
) -> dict:
    return service.set_collection_plan_logo(plan_id, payload)


@router.put("/collections/{plan_id}/species/{species_id}/introduction")
def update_collection_species_introduction(
    plan_id: int,
    species_id: int,
    payload: CollectionSpeciesIntroductionInput,
    service: BirdServiceDependency,
) -> dict:
    return service.update_collection_species_introduction(
        plan_id, species_id, payload
    )


@router.post("/collections/{plan_id}/logo")
async def upload_collection_plan_logo(
    plan_id: int,
    service: BirdServiceDependency,
    photo: Annotated[UploadFile, File()],
    crop_center_x: Annotated[float, Form(ge=0, le=1)] = 0.5,
    crop_center_y: Annotated[float, Form(ge=0, le=1)] = 0.5,
    crop_zoom: Annotated[float, Form(ge=1, le=4)] = 1,
) -> dict:
    try:
        return await service.upload_collection_plan_logo(
            plan_id,
            photo,
            crop_center_x,
            crop_center_y,
            crop_zoom,
        )
    except MediaValidationError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.delete("/collections/{plan_id}/logo")
def clear_collection_plan_logo(
    plan_id: int,
    service: BirdServiceDependency,
) -> dict:
    return service.clear_collection_plan_logo(plan_id)


@router.get("/collections/{plan_id}/species/{species_id}/observations")
def collection_species_observations(
    plan_id: int,
    species_id: int,
    service: BirdServiceDependency,
) -> list[dict]:
    return service.collection_species_observations(plan_id, species_id)


@router.put("/collections/{plan_id}/slots/{slot_id}")
def set_collection_slot_evidence(
    plan_id: int,
    slot_id: int,
    payload: CollectionSlotEvidenceInput,
    service: BirdServiceDependency,
) -> dict:
    return service.set_collection_slot_evidence(plan_id, slot_id, payload)
