from __future__ import annotations

from datetime import UTC, datetime

import pytest
from app.database import Base
from app.enums import (
    IUCNStatus,
    LifeStage,
    MediaKind,
    PhotoType,
    Season,
    Sex,
)
from app.models import (
    Family,
    Genus,
    MediaAsset,
    Observation,
    ObservationPhoto,
    ObservationSpecies,
    Species,
    Subspecies,
    TaxonomicOrder,
)
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


def _session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return Session(engine)


def _taxonomy(session: Session) -> tuple[Species, Species]:
    order = TaxonomicOrder(
        chinese_name="鸻形目",
        scientific_name="Charadriiformes",
        scientific_name_key="charadriiformes",
    )
    family = Family(
        chinese_name="鸥科",
        scientific_name="Laridae",
        scientific_name_key="laridae",
        order=order,
    )
    genus = Genus(
        chinese_name="浮鸥属",
        scientific_name="Chlidonias",
        scientific_name_key="chlidonias",
        family=family,
    )
    first = Species(
        chinese_name="须浮鸥",
        scientific_name="Chlidonias hybrida",
        scientific_name_key="chlidonias hybrida",
        iucn_status=IUCNStatus.LC,
        genus=genus,
    )
    second = Species(
        chinese_name="白翅浮鸥",
        scientific_name="Chlidonias leucopterus",
        scientific_name_key="chlidonias leucopterus",
        iucn_status=IUCNStatus.LC,
        genus=genus,
    )
    session.add_all([first, second])
    session.flush()
    return first, second


def _asset(session: Session, name: str) -> MediaAsset:
    asset = MediaAsset(
        kind=MediaKind.PHOTO,
        sha256=name.ljust(64, "0"),
        relative_path=f"photos/{name}.jpg",
        original_filename=f"{name}.jpg",
        mime_type="image/jpeg",
        byte_size=1024,
    )
    session.add(asset)
    session.flush()
    return asset


def _observation(session: Session, species: Species) -> Observation:
    observation = Observation(
        observed_at=datetime(2026, 11, 4, 8, 30, tzinfo=UTC),
        latitude=31.23,
        longitude=121.47,
        country_code="CN",
        country_name="中国",
        admin1_code="CN-31",
        admin1_name="上海市",
        locality="世纪公园",
        season=Season.AUTUMN,
    )
    session.add(observation)
    session.flush()
    observation.species_entries.append(
        ObservationSpecies(
            species=species,
            photo_type=PhotoType.INDIVIDUAL,
            sex=Sex.UNKNOWN,
            life_stage=LifeStage.ADULT,
            is_primary=True,
        )
    )
    return observation


def test_schema_has_no_legacy_observation_columns_and_has_partial_indexes() -> None:
    session = _session()
    engine = session.get_bind()
    observation_columns = {
        column["name"] for column in inspect(engine).get_columns("observations")
    }
    assert not observation_columns & {
        "species_id",
        "subspecies_id",
        "photo_asset_id",
        "photo_type",
        "sex",
        "life_stage",
    }

    entry_indexes = {
        index["name"] for index in inspect(engine).get_indexes("observation_species")
    }
    photo_indexes = {
        index["name"] for index in inspect(engine).get_indexes("observation_photos")
    }
    assert "uq_observation_species_primary" in entry_indexes
    assert "uq_observation_photos_cover" in photo_indexes


def test_legacy_observation_attributes_are_derived_from_primary_entry_and_cover() -> None:
    session = _session()
    species, _ = _taxonomy(session)
    subspecies = Subspecies(
        chinese_name="指名亚种",
        scientific_name="Chlidonias hybrida hybrida",
        scientific_name_key="chlidonias hybrida hybrida",
        species=species,
    )
    session.add(subspecies)
    asset = _asset(session, "cover")
    observation = _observation(session, species)
    entry = observation.primary_entry
    assert entry is not None
    entry.subspecies = subspecies
    observation.photos.append(
        ObservationPhoto(
            asset=asset,
            observed_at=observation.observed_at,
            position=0,
            is_cover=True,
        )
    )
    session.flush()

    assert observation.species is species
    assert observation.species_id == species.id
    assert observation.subspecies is subspecies
    assert observation.subspecies_id == subspecies.id
    assert observation.photo_type is PhotoType.INDIVIDUAL
    assert observation.sex is Sex.UNKNOWN
    assert observation.life_stage is LifeStage.ADULT
    assert observation.photo_asset is asset
    assert observation.photo_asset_id == asset.id

    entry.sex = Sex.MALE
    session.flush()
    assert observation.sex is Sex.MALE


def test_partial_unique_indexes_reject_second_primary_and_second_cover() -> None:
    session = _session()
    first, second = _taxonomy(session)
    observation = _observation(session, first)
    session.commit()

    observation.species_entries.append(
        ObservationSpecies(
            species=second,
            photo_type=PhotoType.GROUP,
            is_primary=True,
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()

    observation = session.get(Observation, observation.id)
    assert observation is not None
    first_asset = _asset(session, "first")
    second_asset = _asset(session, "second")
    observation.photos.append(
        ObservationPhoto(
            asset=first_asset,
            observed_at=observation.observed_at,
            position=0,
            is_cover=True,
        )
    )
    session.commit()
    observation.photos.append(
        ObservationPhoto(
            asset=second_asset,
            observed_at=observation.observed_at,
            position=1,
            is_cover=True,
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
