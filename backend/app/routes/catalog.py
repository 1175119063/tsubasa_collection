from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import ValidationError

from ..api_dependencies import BirdServiceDependency
from ..media_store import MediaValidationError
from ..schemas import (
    ObservationSelectionInput,
    SpeciesAudioInput,
    SpeciesProfileUpdateInput,
)
from ..taxonomy_service import TaxonomyApplyInput, TaxonomyEditInput, TaxonomyRank

router = APIRouter()


@router.get("/stats")
def stats(service: BirdServiceDependency) -> dict:
    return service.stats()


@router.get("/species")
def list_species(service: BirdServiceDependency) -> list[dict]:
    return service.list_species()


@router.get("/taxonomy/tree")
def taxonomy_tree(service: BirdServiceDependency) -> list[dict]:
    return service.taxonomy_tree()


@router.post("/taxonomy/{rank}/{node_id}/preview")
def preview_taxonomy_edit(
    rank: TaxonomyRank, node_id: int, payload: TaxonomyEditInput, service: BirdServiceDependency,
) -> dict:
    return service.preview_taxonomy_edit(rank, node_id, payload)


@router.put("/taxonomy/{rank}/{node_id}")
def apply_taxonomy_edit(
    rank: TaxonomyRank, node_id: int, payload: TaxonomyApplyInput, service: BirdServiceDependency,
) -> dict:
    return service.apply_taxonomy_edit(rank, node_id, payload)


@router.get("/species/{species_id}/behaviors")
def species_behaviors(species_id: int, service: BirdServiceDependency) -> list[dict]:
    return service.species_detail(species_id)["behaviors"]


@router.get("/species/{species_id}")
def species_detail(species_id: int, service: BirdServiceDependency) -> dict:
    return service.species_detail(species_id)


@router.put("/species/{species_id}/profile")
def update_species_profile(
    species_id: int,
    payload: SpeciesProfileUpdateInput,
    service: BirdServiceDependency,
) -> dict:
    return service.update_species_profile(species_id, payload)


@router.get("/home/cover")
def homepage_cover(service: BirdServiceDependency) -> dict:
    return service.homepage_feature()


@router.put("/home/cover")
def set_homepage_cover(
    payload: ObservationSelectionInput,
    service: BirdServiceDependency,
) -> dict:
    return service.set_homepage_feature(payload.observation_id)


@router.put("/species/{species_id}/cover")
def set_species_cover(
    species_id: int,
    payload: ObservationSelectionInput,
    service: BirdServiceDependency,
) -> dict:
    return service.set_species_cover(species_id, payload.observation_id)


@router.post("/species/{species_id}/audio", status_code=201)
async def add_species_audio(
    species_id: int,
    service: BirdServiceDependency,
    audio: Annotated[UploadFile, File()],
    payload: Annotated[str, Form()] = "{}",
) -> dict:
    try:
        metadata = SpeciesAudioInput.model_validate_json(payload)
    except ValidationError as exc:
        raise HTTPException(422, exc.errors(include_context=False)) from exc
    try:
        link = await service.add_species_audio(species_id, metadata, audio)
    except MediaValidationError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"id": link.id, "asset_id": link.asset_id}


@router.delete("/species/{species_id}/audio/{audio_id}")
def delete_species_audio(
    species_id: int,
    audio_id: int,
    service: BirdServiceDependency,
) -> dict:
    return service.delete_species_audio(species_id, audio_id)
