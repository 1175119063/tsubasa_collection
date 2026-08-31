from __future__ import annotations

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from .collection_service import CollectionServiceMixin
from .enums import (
    MediaKind,
    PhotoType,
)
from .location_trip_service import LocationTripServiceMixin
from .media_store import ImportedMedia, MediaStore
from .models import (
    BirdingLocation,
    Family,
    Genus,
    MediaAsset,
    Observation,
    ObservationAudio,
    ObservationLocationLink,
    ObservationSpecies,
    Species,
    Subspecies,
    TaxonomicOrder,
)
from .observation_service import ObservationServiceMixin
from .schemas import (
    NewSpeciesInput,
    ObservationInput,
    TaxonNodeInput,
)
from .service_common import CreationResult, DomainError, normalized_name
from .species_service import SpeciesServiceMixin


class BirdService(
    CollectionServiceMixin,
    LocationTripServiceMixin,
    ObservationServiceMixin,
    SpeciesServiceMixin,
):
    def __init__(self, session: Session, media_store: MediaStore) -> None:
        self.session = session
        self.media_store = media_store

    async def create_observation(
        self,
        payload: ObservationInput,
        photo: UploadFile,
        audio_files: list[UploadFile] | None = None,
    ) -> CreationResult:
        imported: list[ImportedMedia] = []
        try:
            species = self._resolve_species(payload)
            subspecies = self._resolve_subspecies(species, payload)

            photo_import = await self.media_store.import_photo(self.session, photo)
            imported.append(photo_import)

            observation = Observation(
                species=species,
                subspecies=subspecies,
                photo_asset=photo_import.asset,
                photo_type=payload.photo_type,
                observed_at=payload.observed_at,
                latitude=payload.latitude,
                longitude=payload.longitude,
                country_code=payload.country_code.upper(),
                country_name=payload.country_name,
                admin1_code=payload.admin1_code.upper(),
                admin1_name=payload.admin1_name,
                locality=payload.locality,
                season=payload.season,
                season_note=payload.season_note,
                sex=payload.sex,
                life_stage=payload.life_stage,
                notes=payload.notes,
            )
            self.session.add(observation)
            self.session.flush()
            observation.species_entries.append(
                ObservationSpecies(
                    species=species,
                    subspecies=subspecies,
                    photo_type=payload.photo_type,
                    sex=payload.sex,
                    life_stage=payload.life_stage,
                    is_primary=True,
                )
            )
            for entry_payload in payload.additional_species:
                entry_species = self.session.get(Species, entry_payload.species_id)
                if entry_species is None:
                    raise DomainError("附加物种不存在", 404)
                entry_subspecies = None
                if entry_payload.subspecies_id is not None:
                    entry_subspecies = self.session.get(
                        Subspecies, entry_payload.subspecies_id
                    )
                    if (
                        entry_subspecies is None
                        or entry_subspecies.species_id != entry_species.id
                    ):
                        raise DomainError("附加物种所选亚种不属于该物种", 422)
                observation.species_entries.append(
                    ObservationSpecies(
                        species=entry_species,
                        subspecies=entry_subspecies,
                        photo_type=entry_payload.photo_type,
                        sex=entry_payload.sex,
                        life_stage=entry_payload.life_stage,
                        notes=entry_payload.notes or None,
                        is_primary=False,
                    )
                )

            location = self._resolve_observation_location(payload)
            if location is not None:
                observation.location_link = ObservationLocationLink(location=location)

            linked_audio_ids: set[int] = set()
            for audio in audio_files or []:
                audio_import = await self.media_store.import_audio(self.session, audio)
                imported.append(audio_import)
                if audio_import.asset.id in linked_audio_ids:
                    continue
                linked_audio_ids.add(audio_import.asset.id)
                self.session.add(
                    ObservationAudio(observation=observation, asset=audio_import.asset)
                )

            self.session.commit()
            return CreationResult(observation=observation, species=species)
        except Exception:
            self.session.rollback()
            for item in imported:
                for path in item.created_files:
                    path.unlink(missing_ok=True)
            raise

    def _resolve_observation_location(
        self, payload: ObservationInput
    ) -> BirdingLocation | None:
        if payload.location_id is not None:
            location = self.session.get(BirdingLocation, payload.location_id)
            if location is None:
                raise DomainError("所选观鸟地点不存在", 404)
            return location
        candidates = self.session.scalars(
            select(BirdingLocation).where(
                BirdingLocation.country_code == payload.country_code.upper(),
                BirdingLocation.admin1_code == payload.admin1_code.upper(),
            )
        ).all()
        locality_key = normalized_name(payload.locality)
        return next((item for item in candidates if item.name_key == locality_key), None)

    def _resolve_species(self, payload: ObservationInput) -> Species:
        if payload.species_id is not None:
            species = self.session.scalar(
                select(Species)
                .where(Species.id == payload.species_id)
                .options(selectinload(Species.subspecies))
            )
            if species is None:
                raise DomainError("目标物种不存在", 404)
            return species
        if payload.new_species is None:
            raise DomainError("缺少新物种资料")
        return self._create_species(payload.new_species)

    def _create_species(self, data: NewSpeciesInput) -> Species:
        species_key = normalized_name(data.scientific_name)
        existing = self.session.scalar(
            select(Species).where(Species.scientific_name_key == species_key)
        )
        if existing is not None:
            raise DomainError(f"物种 {data.scientific_name} 已存在", 409)

        order = self._get_or_create_order(data.order)
        family = self._get_or_create_family(data.family, order)
        genus = self._get_or_create_genus(data.genus, family)
        species = Species(
            genus=genus,
            chinese_name=data.chinese_name,
            scientific_name=data.scientific_name,
            scientific_name_key=species_key,
            iucn_status=data.iucn_status,
            china_protection_status=data.china_protection_status,
            has_subspecies=data.has_subspecies,
            notes=data.notes,
        )
        self.session.add(species)
        self.session.flush()

        for item in data.subspecies:
            key = normalized_name(item.scientific_name)
            if self.session.scalar(select(Subspecies).where(Subspecies.scientific_name_key == key)):
                raise DomainError(f"亚种 {item.scientific_name} 已存在", 409)
            species.subspecies.append(
                Subspecies(
                    scientific_name=item.scientific_name,
                    scientific_name_key=key,
                    chinese_name=item.chinese_name,
                )
            )
        self.session.flush()
        return species

    def _get_or_create_order(self, data: TaxonNodeInput) -> TaxonomicOrder:
        key = normalized_name(data.scientific_name)
        node = self.session.scalar(
            select(TaxonomicOrder).where(TaxonomicOrder.scientific_name_key == key)
        )
        if node is None:
            node = TaxonomicOrder(
                chinese_name=data.chinese_name,
                scientific_name=data.scientific_name,
                scientific_name_key=key,
            )
            self.session.add(node)
            self.session.flush()
        return node

    def _get_or_create_family(self, data: TaxonNodeInput, order: TaxonomicOrder) -> Family:
        key = normalized_name(data.scientific_name)
        node = self.session.scalar(select(Family).where(Family.scientific_name_key == key))
        if node is None:
            node = Family(
                order=order,
                chinese_name=data.chinese_name,
                scientific_name=data.scientific_name,
                scientific_name_key=key,
            )
            self.session.add(node)
            self.session.flush()
        elif node.order_id != order.id:
            raise DomainError(f"科 {data.scientific_name} 已属于其他目", 409)
        return node

    def _get_or_create_genus(self, data: TaxonNodeInput, family: Family) -> Genus:
        key = normalized_name(data.scientific_name)
        node = self.session.scalar(select(Genus).where(Genus.scientific_name_key == key))
        if node is None:
            node = Genus(
                family=family,
                chinese_name=data.chinese_name,
                scientific_name=data.scientific_name,
                scientific_name_key=key,
            )
            self.session.add(node)
            self.session.flush()
        elif node.family_id != family.id:
            raise DomainError(f"属 {data.scientific_name} 已属于其他科", 409)
        return node

    def _upsert_profile_order(self, data: TaxonNodeInput) -> TaxonomicOrder:
        key = normalized_name(data.scientific_name)
        node = self.session.scalar(
            select(TaxonomicOrder).where(TaxonomicOrder.scientific_name_key == key)
        )
        if node is None:
            node = TaxonomicOrder(scientific_name_key=key)
            self.session.add(node)
        node.chinese_name = data.chinese_name
        node.scientific_name = data.scientific_name
        self.session.flush()
        return node

    def _upsert_profile_family(
        self, data: TaxonNodeInput, order: TaxonomicOrder
    ) -> Family:
        key = normalized_name(data.scientific_name)
        node = self.session.scalar(select(Family).where(Family.scientific_name_key == key))
        if node is None:
            node = Family(scientific_name_key=key)
            self.session.add(node)
        node.order = order
        node.chinese_name = data.chinese_name
        node.scientific_name = data.scientific_name
        self.session.flush()
        return node

    def _upsert_profile_genus(self, data: TaxonNodeInput, family: Family) -> Genus:
        key = normalized_name(data.scientific_name)
        node = self.session.scalar(select(Genus).where(Genus.scientific_name_key == key))
        if node is None:
            node = Genus(scientific_name_key=key)
            self.session.add(node)
        node.family = family
        node.chinese_name = data.chinese_name
        node.scientific_name = data.scientific_name
        self.session.flush()
        return node

    def _resolve_subspecies(self, species: Species, payload: ObservationInput) -> Subspecies | None:
        if payload.photo_type is PhotoType.GROUP:
            return None
        if not species.has_subspecies:
            if payload.subspecies_id is not None or payload.subspecies_scientific_name is not None:
                raise DomainError("该物种无亚种，不能选择亚种")
            return None
        if payload.subspecies_id is not None:
            subspecies = self.session.get(Subspecies, payload.subspecies_id)
            if subspecies is None or subspecies.species_id != species.id:
                raise DomainError("所选亚种不属于目标物种")
            return subspecies
        if payload.subspecies_scientific_name is not None:
            key = normalized_name(payload.subspecies_scientific_name)
            subspecies = self.session.scalar(
                select(Subspecies).where(
                    Subspecies.species_id == species.id,
                    Subspecies.scientific_name_key == key,
                )
            )
            if subspecies is None:
                raise DomainError("所选亚种不在新物种的完整亚种名单中")
            return subspecies
        return None

    def stats(self) -> dict:
        return {
            "species_count": self.session.scalar(select(func.count(Species.id))) or 0,
            "observation_count": self.session.scalar(select(func.count(Observation.id))) or 0,
            "photo_count": self.session.scalar(
                select(func.count(Observation.photo_asset_id))
            )
            or 0,
            "audio_count": self.session.scalar(
                select(func.count(MediaAsset.id)).where(MediaAsset.kind == MediaKind.AUDIO)
            )
            or 0,
        }
