from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass

from fastapi import UploadFile
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from .enums import (
    BodySize,
    EcologicalGroup,
    EvidenceDimension,
    LifeStage,
    MediaKind,
    PhotoType,
    Sex,
)
from .media_store import ImportedMedia, MediaStore
from .models import (
    BirdingLocation,
    BirdingTrip,
    EvidenceSelection,
    Family,
    Genus,
    HomeDisplayPreference,
    LocationCover,
    MediaAsset,
    Observation,
    ObservationAudio,
    ObservationLocationLink,
    ObservationSpecies,
    ObservationTripLink,
    Species,
    SpeciesAudio,
    SpeciesBehaviorTag,
    SpeciesDisplayPreference,
    SpeciesEcologyProfile,
    SpeciesHabitatPreference,
    SpeciesIndividualTag,
    Subspecies,
    TaxonomicOrder,
    TripLocation,
)
from .schemas import (
    LocationInput,
    LocationObservationSelectionInput,
    NewSpeciesInput,
    ObservationInput,
    ObservationSpeciesInput,
    ObservationUpdateInput,
    SpeciesAudioInput,
    SpeciesProfileUpdateInput,
    TaxonNodeInput,
    TripInput,
    TripObservationSelectionInput,
)


class DomainError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def normalized_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    return re.sub(r"\s+", " ", normalized.strip()).casefold()


@dataclass
class CreationResult:
    observation: Observation
    species: Species


class BirdService:
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

    async def add_species_audio(
        self, species_id: int, payload: SpeciesAudioInput, upload: UploadFile
    ) -> SpeciesAudio:
        species = self.session.get(Species, species_id)
        if species is None:
            raise DomainError("物种不存在", 404)
        imported: ImportedMedia | None = None
        try:
            imported = await self.media_store.import_audio(self.session, upload)
            existing = self.session.scalar(
                select(SpeciesAudio).where(
                    SpeciesAudio.species_id == species_id,
                    SpeciesAudio.asset_id == imported.asset.id,
                )
            )
            if existing is not None:
                raise DomainError("该录音已添加到此物种", 409)
            link = SpeciesAudio(
                species=species,
                asset=imported.asset,
                title=payload.title,
                notes=payload.notes,
                recorded_at=payload.recorded_at,
                locality=payload.locality,
            )
            self.session.add(link)
            self.session.commit()
            return link
        except Exception:
            self.session.rollback()
            if imported is not None:
                for path in imported.created_files:
                    path.unlink(missing_ok=True)
            raise

    def list_species(self) -> list[dict]:
        species_list = self.session.scalars(
            select(Species)
            .options(
                selectinload(Species.genus).selectinload(Genus.family).selectinload(Family.order),
                selectinload(Species.observations).selectinload(Observation.photo_asset),
                selectinload(Species.observation_entries)
                .selectinload(ObservationSpecies.observation)
                .selectinload(Observation.photo_asset),
                selectinload(Species.observation_entries).selectinload(
                    ObservationSpecies.subspecies
                ),
                selectinload(Species.observation_entries)
                .selectinload(ObservationSpecies.observation)
                .selectinload(Observation.photo_asset),
                selectinload(Species.display_preference),
            )
            .order_by(Species.id)
        ).all()
        return [self._species_summary(item) for item in species_list if item.observation_entries]

    def taxonomy_tree(self) -> list[dict]:
        orders = self.session.scalars(
            select(TaxonomicOrder)
            .options(selectinload(TaxonomicOrder.families).selectinload(Family.genera))
            .order_by(TaxonomicOrder.chinese_name, TaxonomicOrder.id)
        ).all()
        return [
            {
                "id": order.id,
                "chinese_name": order.chinese_name,
                "scientific_name": order.scientific_name,
                "families": [
                    {
                        "id": family.id,
                        "chinese_name": family.chinese_name,
                        "scientific_name": family.scientific_name,
                        "genera": [
                            {
                                "id": genus.id,
                                "chinese_name": genus.chinese_name,
                                "scientific_name": genus.scientific_name,
                            }
                            for genus in sorted(
                                family.genera,
                                key=lambda item: (item.chinese_name, item.id),
                            )
                        ],
                    }
                    for family in sorted(
                        order.families,
                        key=lambda item: (item.chinese_name, item.id),
                    )
                ],
            }
            for order in orders
        ]

    def _species_summary(self, species: Species) -> dict:
        observations = sorted(
            (entry.observation for entry in species.observation_entries),
            key=lambda item: (item.observed_at, item.id),
        )
        cover = self._selected_observation(
            observations,
            species.display_preference.cover_observation_id if species.display_preference else None,
        )
        return {
            "id": species.id,
            "catalog_number": species.catalog_number,
            "chinese_name": species.chinese_name,
            "scientific_name": species.scientific_name,
            "family_id": species.genus.family_id,
            "genus_id": species.genus_id,
            "order_name": species.genus.family.order.chinese_name,
            "family_name": species.genus.family.chinese_name,
            "family_scientific_name": species.genus.family.scientific_name,
            "genus_name": species.genus.chinese_name,
            "genus_scientific_name": species.genus.scientific_name,
            "iucn_status": species.iucn_status.value,
            "china_protection_status": (
                species.china_protection_status.value if species.china_protection_status else None
            ),
            "observation_count": len(observations),
            "cover_asset_id": cover.photo_asset_id,
            "cover_url": self._media_url(cover.photo_asset, thumbnail=True),
            "first_observed_at": observations[0].observed_at.isoformat(timespec="minutes"),
        }

    def species_detail(self, species_id: int) -> dict:
        species = self.session.scalar(
            select(Species)
            .where(Species.id == species_id)
            .options(
                selectinload(Species.genus).selectinload(Genus.family).selectinload(Family.order),
                selectinload(Species.subspecies),
                selectinload(Species.observations).selectinload(Observation.photo_asset),
                selectinload(Species.observations).selectinload(Observation.subspecies),
                selectinload(Species.observations)
                .selectinload(Observation.audio_links)
                .selectinload(ObservationAudio.asset),
                selectinload(Species.observations)
                .selectinload(Observation.location_link)
                .selectinload(ObservationLocationLink.location),
                selectinload(Species.observations)
                .selectinload(Observation.trip_link)
                .selectinload(ObservationTripLink.trip)
                .selectinload(BirdingTrip.location),
                selectinload(Species.audio_links).selectinload(SpeciesAudio.asset),
                selectinload(Species.display_preference),
                selectinload(Species.ecology_profile),
                selectinload(Species.habitat_preferences),
                selectinload(Species.evidence_selections),
                selectinload(Species.behavior_tags).selectinload(
                    SpeciesBehaviorTag.observation
                ),
                selectinload(Species.individual_tags).selectinload(
                    SpeciesIndividualTag.observation
                ),
            )
        )
        if species is None or not species.observation_entries:
            raise DomainError("物种不存在", 404)

        entries_by_observation = {
            entry.observation_id: entry for entry in species.observation_entries
        }
        observations = sorted(
            (entry.observation for entry in species.observation_entries),
            key=lambda item: (item.observed_at, item.id),
        )
        preference = species.display_preference
        cover = self._selected_observation(
            observations, preference.cover_observation_id if preference else None
        )
        first = self._selected_observation(
            observations, preference.first_encounter_observation_id if preference else None
        )

        countries: dict[str, dict] = {}
        admin1_regions: dict[str, dict] = {}
        seasons: dict[str, dict] = {}
        sexes: dict[str, dict] = {}
        life_stages: dict[str, dict] = {}
        captured_subspecies: dict[int, dict] = {}
        for item in observations:
            species_entry = entries_by_observation[item.id]
            proof = self._proof(item)
            countries.setdefault(
                item.country_code,
                {"code": item.country_code, "name": item.country_name, **proof},
            )
            admin_key = f"{item.country_code}:{item.admin1_code}"
            admin1_regions.setdefault(
                admin_key,
                {"code": item.admin1_code, "name": item.admin1_name, **proof},
            )
            seasons.setdefault(item.season.value, {"value": item.season.value, **proof})
            if species_entry.sex is not None and species_entry.sex is not Sex.UNKNOWN:
                sexes.setdefault(
                    species_entry.sex.value,
                    {"value": species_entry.sex.value, **proof},
                )
            if (
                species_entry.life_stage is not None
                and species_entry.life_stage is not LifeStage.UNKNOWN
            ):
                life_stages.setdefault(
                    species_entry.life_stage.value,
                    {"value": species_entry.life_stage.value, **proof},
                )
            if species_entry.subspecies_id is not None:
                captured_subspecies.setdefault(species_entry.subspecies_id, proof)

        selected_evidence = {
            (item.dimension, item.value_key): item.observation_id
            for item in species.evidence_selections
        }
        observations_by_id = {item.id: item for item in observations}
        for value, entry in sexes.items():
            entry.update(
                self._selected_archive_proof(
                    entry,
                    selected_evidence,
                    EvidenceDimension.SEX,
                    value,
                    observations_by_id,
                    species.id,
                )
            )
        for value, entry in life_stages.items():
            entry.update(
                self._selected_archive_proof(
                    entry,
                    selected_evidence,
                    EvidenceDimension.LIFE_STAGE,
                    value,
                    observations_by_id,
                    species.id,
                )
            )

        result = self._species_summary(species)
        result.update(
            {
                "classification": {
                    "order": {
                        "chinese_name": species.genus.family.order.chinese_name,
                        "scientific_name": species.genus.family.order.scientific_name,
                    },
                    "family": {
                        "chinese_name": species.genus.family.chinese_name,
                        "scientific_name": species.genus.family.scientific_name,
                    },
                    "genus": {
                        "chinese_name": species.genus.chinese_name,
                        "scientific_name": species.genus.scientific_name,
                    },
                },
                "introduction": species.notes,
                "ecology": {
                    "group": (
                        species.ecology_profile.ecological_group.value
                        if species.ecology_profile
                        else EcologicalGroup.UNKNOWN.value
                    ),
                    "body_size": (
                        species.ecology_profile.body_size.value
                        if species.ecology_profile
                        else BodySize.UNKNOWN.value
                    ),
                    "habitats": sorted(
                        item.habitat.value for item in species.habitat_preferences
                    ),
                },
                "has_subspecies": species.has_subspecies,
                "subspecies": [
                    {
                        "id": item.id,
                        "chinese_name": item.chinese_name,
                        "scientific_name": item.scientific_name,
                        "captured": item.id in captured_subspecies,
                        **(
                            self._selected_archive_proof(
                                captured_subspecies[item.id],
                                selected_evidence,
                                EvidenceDimension.SUBSPECIES,
                                str(item.id),
                                observations_by_id,
                                species.id,
                            )
                            if item.id in captured_subspecies
                            else {}
                        ),
                    }
                    for item in sorted(species.subspecies, key=lambda value: value.scientific_name)
                ],
                "cover": self._proof(cover),
                "first_encounter": {
                    **self._proof(first),
                    "observed_at": first.observed_at.isoformat(timespec="minutes"),
                    "country_name": first.country_name,
                    "admin1_name": first.admin1_name,
                    "locality": first.locality,
                },
                "collected": {
                    "countries": list(countries.values()),
                    "admin1_regions": list(admin1_regions.values()),
                    "seasons": list(seasons.values()),
                    "sexes": list(sexes.values()),
                    "life_stages": list(life_stages.values()),
                },
                "observations": [
                    self._observation_dict(item, species_id=species.id)
                    for item in observations
                ],
                "behaviors": [
                    {
                        "id": item.id,
                        "label": item.label,
                        "linked": item.observation_id is not None,
                        **(
                            self._proof(item.observation)
                            if item.observation is not None
                            else {}
                        ),
                    }
                    for item in sorted(
                        species.behavior_tags,
                        key=lambda value: (value.created_at, value.id),
                    )
                ],
                "individuals": [
                    *[
                        {
                            "id": f"observed-{item['value']}",
                            "label": item["label"],
                            "linked": item.get("observation_id") is not None,
                            **(
                                {"observation_id": item["observation_id"]}
                                if item.get("observation_id") is not None
                                else {}
                            ),
                        }
                        for item in [
                            *[
                                {
                                    "value": value,
                                    "label": f"性别 · {value}",
                                    **entry,
                                }
                                for value, entry in sexes.items()
                            ],
                            *[
                                {
                                    "value": value,
                                    "label": f"生命阶段 · {value}",
                                    **entry,
                                }
                                for value, entry in life_stages.items()
                            ],
                        ]
                    ],
                    *[
                        {
                            "id": item.id,
                            "label": item.label,
                            "linked": item.observation_id is not None,
                            **(
                                self._proof(item.observation)
                                if item.observation is not None
                                else {}
                            ),
                        }
                        for item in sorted(
                            species.individual_tags,
                            key=lambda value: (value.created_at, value.id),
                        )
                    ],
                ],
                "species_audio": [
                    {
                        "id": item.id,
                        "title": item.title,
                        "notes": item.notes,
                        "recorded_at": (
                            item.recorded_at.isoformat(timespec="minutes")
                            if item.recorded_at
                            else None
                        ),
                        "locality": item.locality,
                        "asset_id": item.asset_id,
                        "url": self._media_url(item.asset),
                    }
                    for item in species.audio_links
                ],
            }
        )
        return result

    def update_species_profile(
        self, species_id: int, payload: SpeciesProfileUpdateInput
    ) -> dict:
        species = self.session.scalar(
            select(Species)
            .where(Species.id == species_id)
            .options(
                selectinload(Species.genus)
                .selectinload(Genus.family)
                .selectinload(Family.order),
                selectinload(Species.observations),
                selectinload(Species.observation_entries).selectinload(
                    ObservationSpecies.observation
                ),
                selectinload(Species.subspecies),
                selectinload(Species.evidence_selections),
                selectinload(Species.behavior_tags),
                selectinload(Species.individual_tags),
                selectinload(Species.ecology_profile),
                selectinload(Species.habitat_preferences),
            )
        )
        if species is None or not species.observation_entries:
            raise DomainError("物种不存在", 404)

        observations_by_id = {
            entry.observation_id: entry.observation for entry in species.observation_entries
        }
        for selection in payload.evidence_selections:
            observation = observations_by_id.get(selection.observation_id)
            if observation is None:
                raise DomainError("所选档案凭证不属于该物种", 422)
            if not self._observation_matches_archive(
                observation, selection.dimension, selection.value_key, species.id
            ):
                raise DomainError("所选观察与对应档案项不一致", 422)
        for behavior in payload.behaviors:
            if (
                behavior.observation_id is not None
                and behavior.observation_id not in observations_by_id
            ):
                raise DomainError("行为标签只能关联该物种的观察记录", 422)

        individual_keys = [normalized_name(item.label) for item in payload.individuals]
        if len(individual_keys) != len(set(individual_keys)):
            raise DomainError("涓綋鏍囩涓嶈兘閲嶅", 422)
        for individual in payload.individuals:
            if (
                individual.observation_id is not None
                and individual.observation_id not in observations_by_id
            ):
                raise DomainError("涓綋鏍囩鍙兘鍏宠仈璇ョ墿绉嶇殑瑙傚療璁板綍", 422)

        old_genus_id = species.genus_id
        old_family_id = species.genus.family_id
        old_order_id = species.genus.family.order_id
        order = self._upsert_profile_order(payload.order)
        family = self._upsert_profile_family(payload.family, order)
        genus = self._upsert_profile_genus(payload.genus, family)
        species.genus = genus
        species.notes = payload.introduction or None
        if species.ecology_profile is None:
            species.ecology_profile = SpeciesEcologyProfile(
                ecological_group=payload.ecological_group,
                body_size=payload.body_size,
            )
        else:
            species.ecology_profile.ecological_group = payload.ecological_group
            species.ecology_profile.body_size = payload.body_size

        self.session.execute(
            delete(EvidenceSelection).where(EvidenceSelection.species_id == species.id)
        )
        self.session.execute(
            delete(SpeciesBehaviorTag).where(SpeciesBehaviorTag.species_id == species.id)
        )
        self.session.execute(
            delete(SpeciesIndividualTag).where(SpeciesIndividualTag.species_id == species.id)
        )
        self.session.execute(
            delete(SpeciesHabitatPreference).where(
                SpeciesHabitatPreference.species_id == species.id
            )
        )
        self.session.flush()
        for selection in payload.evidence_selections:
            self.session.add(
                EvidenceSelection(
                    species_id=species.id,
                    observation_id=selection.observation_id,
                    dimension=selection.dimension,
                    value_key=selection.value_key,
                )
            )
        for behavior in payload.behaviors:
            self.session.add(
                SpeciesBehaviorTag(
                    species_id=species.id,
                    label=behavior.label,
                    label_key=normalized_name(behavior.label),
                    observation_id=behavior.observation_id,
                )
            )
        for individual in payload.individuals:
            self.session.add(
                SpeciesIndividualTag(
                    species_id=species.id,
                    label=individual.label,
                    label_key=normalized_name(individual.label),
                    observation_id=individual.observation_id,
                )
            )
        for habitat in payload.preferred_habitats:
            self.session.add(
                SpeciesHabitatPreference(species_id=species.id, habitat=habitat)
            )

        self.session.flush()
        if (old_genus_id, old_family_id, old_order_id) != (
            genus.id,
            family.id,
            order.id,
        ):
            self._prune_taxonomy(old_genus_id, old_family_id, old_order_id)
        self.session.commit()
        self.session.expire_all()
        return self.species_detail(species_id)

    def set_species_cover(self, species_id: int, observation_id: int | None) -> dict:
        species = self.session.scalar(
            select(Species)
            .where(Species.id == species_id)
            .options(
                selectinload(Species.observations),
                selectinload(Species.observation_entries).selectinload(
                    ObservationSpecies.observation
                ),
                selectinload(Species.display_preference),
            )
        )
        if species is None or not species.observation_entries:
            raise DomainError("物种不存在", 404)
        if observation_id is not None and not any(
            item.observation_id == observation_id for item in species.observation_entries
        ):
            raise DomainError("所选观察记录不属于该物种", 422)

        preference = species.display_preference
        if preference is None:
            preference = SpeciesDisplayPreference(species=species)
            self.session.add(preference)
        preference.cover_observation_id = observation_id
        self.session.commit()

        observations = sorted(
            (entry.observation for entry in species.observation_entries),
            key=lambda item: (item.observed_at, item.id),
        )
        selected = self._selected_observation(observations, observation_id)
        return {
            "species_id": species_id,
            "cover_observation_id": selected.id,
            "cover_asset_id": selected.photo_asset_id,
        }

    def create_location(self, payload: LocationInput) -> dict:
        name_key = normalized_name(payload.name)
        country_code = payload.country_code.upper()
        admin1_code = payload.admin1_code.upper()
        existing = self.session.scalar(
            select(BirdingLocation).where(
                BirdingLocation.country_code == country_code,
                BirdingLocation.admin1_code == admin1_code,
                BirdingLocation.name_key == name_key,
            )
        )
        if existing is not None:
            raise DomainError("该行政区内已存在同名地点", 409)
        location = BirdingLocation(
            name=payload.name,
            name_key=name_key,
            location_type=payload.location_type,
            country_code=country_code,
            country_name=payload.country_name,
            admin1_code=admin1_code,
            admin1_name=payload.admin1_name,
            city=payload.city or None,
            district=payload.district or None,
            center_latitude=payload.center_latitude,
            center_longitude=payload.center_longitude,
            coordinate_system=payload.coordinate_system,
            radius_meters=payload.radius_meters,
            notes=payload.notes or None,
        )
        self.session.add(location)
        self.session.flush()
        if payload.link_matching_records:
            candidates = self.session.scalars(
                select(Observation)
                .where(
                    Observation.country_code == country_code,
                    Observation.admin1_code == admin1_code,
                )
                .options(selectinload(Observation.location_link))
            ).all()
            for observation in candidates:
                if (
                    observation.location_link is None
                    and normalized_name(observation.locality) == name_key
                ):
                    observation.location_link = ObservationLocationLink(location=location)
        self.session.commit()
        return self.location_detail(location.id)

    def list_locations(self) -> list[dict]:
        locations = self.session.scalars(
            select(BirdingLocation)
            .options(
                selectinload(BirdingLocation.observation_links)
                .selectinload(ObservationLocationLink.observation)
                .selectinload(Observation.species),
                selectinload(BirdingLocation.observation_links)
                .selectinload(ObservationLocationLink.observation)
                .selectinload(Observation.photo_asset),
                selectinload(BirdingLocation.cover).selectinload(LocationCover.asset),
                selectinload(BirdingLocation.trips),
                selectinload(BirdingLocation.trip_links),
            )
            .order_by(BirdingLocation.id)
        ).all()
        return [self._location_summary(item) for item in locations]

    def location_detail(self, location_id: int) -> dict:
        location = self.session.scalar(
            select(BirdingLocation)
            .where(BirdingLocation.id == location_id)
            .options(
                selectinload(BirdingLocation.observation_links)
                .selectinload(ObservationLocationLink.observation)
                .selectinload(Observation.species),
                selectinload(BirdingLocation.observation_links)
                .selectinload(ObservationLocationLink.observation)
                .selectinload(Observation.subspecies),
                selectinload(BirdingLocation.observation_links)
                .selectinload(ObservationLocationLink.observation)
                .selectinload(Observation.photo_asset),
                selectinload(BirdingLocation.observation_links)
                .selectinload(ObservationLocationLink.observation)
                .selectinload(Observation.audio_links)
                .selectinload(ObservationAudio.asset),
                selectinload(BirdingLocation.cover).selectinload(LocationCover.asset),
                selectinload(BirdingLocation.trips),
                selectinload(BirdingLocation.trip_links)
                .selectinload(TripLocation.trip)
                .selectinload(BirdingTrip.location),
                selectinload(BirdingLocation.trip_links)
                .selectinload(TripLocation.trip)
                .selectinload(BirdingTrip.observation_links),
                selectinload(BirdingLocation.observation_links)
                .selectinload(ObservationLocationLink.observation)
                .selectinload(Observation.trip_link)
                .selectinload(ObservationTripLink.trip)
                .selectinload(BirdingTrip.location),
            )
        )
        if location is None:
            raise DomainError("观鸟地点不存在", 404)
        observations = sorted(
            (link.observation for link in location.observation_links),
            key=lambda item: (item.observed_at, item.id),
        )
        monthly: dict[str, dict] = defaultdict(
            lambda: {"visit_days": set(), "observation_count": 0}
        )
        species: dict[int, dict] = {}
        for observation in observations:
            month = observation.observed_at.strftime("%Y-%m")
            monthly[month]["visit_days"].add(observation.observed_at.date().isoformat())
            monthly[month]["observation_count"] += 1
            for species_entry in observation.species_entries:
                entry = species.setdefault(
                    species_entry.species_id,
                    {
                        "id": species_entry.species_id,
                        "chinese_name": species_entry.species.chinese_name,
                        "scientific_name": species_entry.species.scientific_name,
                        "observation_count": 0,
                        "thumbnail_url": self._media_url(
                            observation.photo_asset, thumbnail=True
                        ),
                    },
                )
                entry["observation_count"] += 1
        result = self._location_summary(location)
        related_trips = sorted(
            (link.trip for link in location.trip_links),
            key=lambda item: (item.started_at, item.id),
            reverse=True,
        )
        result.update(
            {
                "monthly_activity": [
                    {
                        "month": month,
                        "visit_day_count": len(values["visit_days"]),
                        "observation_count": values["observation_count"],
                    }
                    for month, values in sorted(monthly.items())
                ],
                "species": list(species.values()),
                "observations": [self._observation_dict(item) for item in observations],
                "trips": [
                    {
                        "id": trip.id,
                        "catalog_number": trip.catalog_number,
                        "name": trip.name or trip.location.name,
                        "started_at": trip.started_at.isoformat(timespec="minutes"),
                        "ended_at": trip.ended_at.isoformat(timespec="minutes"),
                        "observation_count": len(trip.observation_links),
                        "is_primary_location": trip.location_id == location.id,
                    }
                    for trip in related_trips
                ],
            }
        )
        return result

    def update_location(self, location_id: int, payload: LocationInput) -> dict:
        location = self.session.get(BirdingLocation, location_id)
        if location is None:
            raise DomainError("观鸟地点不存在", 404)
        name_key = normalized_name(payload.name)
        country_code = payload.country_code.upper()
        admin1_code = payload.admin1_code.upper()
        duplicate = self.session.scalar(
            select(BirdingLocation).where(
                BirdingLocation.id != location_id,
                BirdingLocation.country_code == country_code,
                BirdingLocation.admin1_code == admin1_code,
                BirdingLocation.name_key == name_key,
            )
        )
        if duplicate is not None:
            raise DomainError("该行政区内已存在同名地点", 409)
        location.name = payload.name
        location.name_key = name_key
        location.location_type = payload.location_type
        location.country_code = country_code
        location.country_name = payload.country_name
        location.admin1_code = admin1_code
        location.admin1_name = payload.admin1_name
        location.city = payload.city or None
        location.district = payload.district or None
        location.center_latitude = payload.center_latitude
        location.center_longitude = payload.center_longitude
        location.coordinate_system = payload.coordinate_system
        location.radius_meters = payload.radius_meters
        location.notes = payload.notes or None
        self.session.commit()
        return self.location_detail(location_id)

    async def set_location_cover(self, location_id: int, upload: UploadFile) -> dict:
        location = self.session.scalar(
            select(BirdingLocation)
            .where(BirdingLocation.id == location_id)
            .options(selectinload(BirdingLocation.cover))
        )
        if location is None:
            raise DomainError("观鸟地点不存在", 404)
        imported: ImportedMedia | None = None
        old_asset_id = location.cover.asset_id if location.cover else None
        try:
            imported = await self.media_store.import_photo(self.session, upload)
            if location.cover is None:
                location.cover = LocationCover(asset=imported.asset)
            else:
                location.cover.asset = imported.asset
            self.session.commit()
        except Exception:
            self.session.rollback()
            if imported is not None:
                for path in imported.created_files:
                    path.unlink(missing_ok=True)
            raise
        if old_asset_id is not None and old_asset_id != imported.asset.id:
            self._remove_unreferenced_assets({old_asset_id})
        return self.location_detail(location_id)

    def create_trip(self, payload: TripInput) -> dict:
        locations = self._trip_payload_locations(payload)
        primary = next(item for item in locations if item.id == payload.primary_location_id)
        trip = BirdingTrip(
            name=payload.name or None,
            location=primary,
            started_at=payload.started_at,
            ended_at=payload.ended_at,
            notes=payload.notes or None,
        )
        trip.location_links = [
            TripLocation(
                location=location,
                visit_order=index,
                is_primary=location.id == payload.primary_location_id,
            )
            for index, location in enumerate(locations, 1)
        ]
        self.session.add(trip)
        self.session.commit()
        return self.trip_detail(trip.id)

    def _trip_payload_locations(self, payload: TripInput) -> list[BirdingLocation]:
        locations = self.session.scalars(
            select(BirdingLocation).where(BirdingLocation.id.in_(payload.location_ids))
        ).all()
        by_id = {item.id: item for item in locations}
        if len(by_id) != len(payload.location_ids):
            raise DomainError("远征地点中存在无效地点", 404)
        return [by_id[location_id] for location_id in payload.location_ids]

    def list_trips(self) -> list[dict]:
        trips = self.session.scalars(
            select(BirdingTrip)
            .options(
                selectinload(BirdingTrip.location),
                selectinload(BirdingTrip.location_links).selectinload(TripLocation.location),
                selectinload(BirdingTrip.observation_links)
                .selectinload(ObservationTripLink.observation)
                .selectinload(Observation.species)
                .selectinload(Species.genus)
                .selectinload(Genus.family),
                selectinload(BirdingTrip.observation_links)
                .selectinload(ObservationTripLink.observation)
                .selectinload(Observation.photo_asset),
            )
            .order_by(BirdingTrip.started_at, BirdingTrip.id)
        ).all()
        return [self._trip_summary(item) for item in trips]

    def trip_detail(self, trip_id: int) -> dict:
        trip = self.session.scalar(
            select(BirdingTrip)
            .where(BirdingTrip.id == trip_id)
            .options(
                selectinload(BirdingTrip.location),
                selectinload(BirdingTrip.location_links).selectinload(TripLocation.location),
                selectinload(BirdingTrip.observation_links)
                .selectinload(ObservationTripLink.observation)
                .selectinload(Observation.species)
                .selectinload(Species.genus)
                .selectinload(Genus.family),
                selectinload(BirdingTrip.observation_links)
                .selectinload(ObservationTripLink.observation)
                .selectinload(Observation.subspecies),
                selectinload(BirdingTrip.observation_links)
                .selectinload(ObservationTripLink.observation)
                .selectinload(Observation.photo_asset),
                selectinload(BirdingTrip.observation_links)
                .selectinload(ObservationTripLink.observation)
                .selectinload(Observation.audio_links)
                .selectinload(ObservationAudio.asset),
                selectinload(BirdingTrip.observation_links)
                .selectinload(ObservationTripLink.observation)
                .selectinload(Observation.location_link)
                .selectinload(ObservationLocationLink.location),
            )
        )
        if trip is None:
            raise DomainError("观鸟行程不存在", 404)
        observations = sorted(
            (link.observation for link in trip.observation_links),
            key=lambda item: (item.observed_at, item.id),
        )
        species: dict[int, dict] = {}
        for observation in observations:
            for species_entry in observation.species_entries:
                entry = species.setdefault(
                    species_entry.species_id,
                    {
                        "id": species_entry.species_id,
                        "chinese_name": species_entry.species.chinese_name,
                        "scientific_name": species_entry.species.scientific_name,
                        "observation_count": 0,
                        "thumbnail_url": self._media_url(
                            observation.photo_asset, thumbnail=True
                        ),
                    },
                )
                entry["observation_count"] += 1
        result = self._trip_summary(trip)
        result.update(
            {
                "species": list(species.values()),
                "observations": [self._observation_dict(item) for item in observations],
            }
        )
        return result

    def update_trip(self, trip_id: int, payload: TripInput) -> dict:
        trip = self.session.scalar(
            select(BirdingTrip)
            .where(BirdingTrip.id == trip_id)
            .options(
                selectinload(BirdingTrip.observation_links)
                .selectinload(ObservationTripLink.observation)
                .selectinload(Observation.location_link),
                selectinload(BirdingTrip.location_links),
            )
        )
        if trip is None:
            raise DomainError("观鸟行程不存在", 404)
        locations = self._trip_payload_locations(payload)
        location_ids = {item.id for item in locations}
        primary = next(item for item in locations if item.id == payload.primary_location_id)
        for link in trip.observation_links:
            observation = link.observation
            if not payload.started_at <= observation.observed_at <= payload.ended_at:
                raise DomainError("新的行程时间无法包含当前全部关联观察", 422)
            if (
                observation.location_link is not None
                and observation.location_link.location_id not in location_ids
            ):
                raise DomainError("新的远征地点无法包含当前全部关联观察", 422)
        trip.location = primary
        trip.location_links.clear()
        self.session.flush()
        trip.location_links.extend(
            TripLocation(
                location=location,
                visit_order=index,
                is_primary=location.id == payload.primary_location_id,
            )
            for index, location in enumerate(locations, 1)
        )
        trip.name = payload.name or None
        trip.started_at = payload.started_at
        trip.ended_at = payload.ended_at
        trip.notes = payload.notes or None
        self.session.commit()
        return self.trip_detail(trip_id)

    def set_trip_observations(
        self, trip_id: int, payload: TripObservationSelectionInput
    ) -> dict:
        trip = self.session.scalar(
            select(BirdingTrip)
            .where(BirdingTrip.id == trip_id)
            .options(
                selectinload(BirdingTrip.observation_links),
                selectinload(BirdingTrip.location_links),
            )
        )
        if trip is None:
            raise DomainError("观鸟行程不存在", 404)
        location_ids = {link.location_id for link in trip.location_links} or {trip.location_id}
        selected_ids = set(payload.observation_ids)
        observations = (
            self.session.scalars(
                select(Observation)
                .where(Observation.id.in_(selected_ids))
                .options(
                    selectinload(Observation.location_link),
                    selectinload(Observation.trip_link),
                )
            ).all()
            if selected_ids
            else []
        )
        if len(observations) != len(selected_ids):
            raise DomainError("所选观察记录中存在无效记录", 422)
        for observation in observations:
            if not trip.started_at <= observation.observed_at <= trip.ended_at:
                raise DomainError("所选观察时间不在行程范围内", 422)
            if (
                observation.trip_link is not None
                and observation.trip_link.trip_id != trip_id
            ):
                raise DomainError("所选观察已经属于其他观鸟行程", 409)
            if (
                observation.location_link is not None
                and observation.location_link.location_id not in location_ids
            ):
                raise DomainError("所选观察地点不属于该远征路线", 422)
        self.session.execute(
            delete(ObservationTripLink).where(
                ObservationTripLink.trip_id == trip_id,
                ObservationTripLink.observation_id.not_in(selected_ids),
            )
        )
        for observation in observations:
            if observation.location_link is None:
                observation.location_link = ObservationLocationLink(
                    location_id=trip.location_id
                )
            if observation.trip_link is None:
                observation.trip_link = ObservationTripLink(trip_id=trip_id)
        if trip.cover_observation_id not in selected_ids:
            trip.cover_observation_id = None
        self.session.commit()
        self.session.expire_all()
        return self.trip_detail(trip_id)

    def set_trip_cover(self, trip_id: int, observation_id: int | None) -> dict:
        trip = self.session.scalar(
            select(BirdingTrip)
            .where(BirdingTrip.id == trip_id)
            .options(
                selectinload(BirdingTrip.observation_links)
                .selectinload(ObservationTripLink.observation)
            )
        )
        if trip is None:
            raise DomainError("观鸟行程不存在", 404)
        observations = [link.observation for link in trip.observation_links]
        if observation_id is not None and not any(
            item.id == observation_id for item in observations
        ):
            raise DomainError("所选封面观察不属于该行程", 422)
        trip.cover_observation_id = observation_id
        self.session.commit()
        selected = self._selected_trip_observation(observations, observation_id)
        return {
            "trip_id": trip_id,
            "cover_observation_id": selected.id if selected else None,
            "cover_asset_id": selected.photo_asset_id if selected else None,
        }

    def delete_trip(self, trip_id: int) -> dict:
        trip = self.session.scalar(
            select(BirdingTrip)
            .where(BirdingTrip.id == trip_id)
            .options(selectinload(BirdingTrip.observation_links))
        )
        if trip is None:
            raise DomainError("观鸟行程不存在", 404)
        unlinked_count = len(trip.observation_links)
        self.session.delete(trip)
        self.session.commit()
        return {"deleted_trip_id": trip_id, "unlinked_observation_count": unlinked_count}

    def _trip_summary(self, trip: BirdingTrip) -> dict:
        observations = sorted(
            (link.observation for link in trip.observation_links),
            key=lambda item: (item.observed_at, item.id),
        )
        entries = [entry for item in observations for entry in item.species_entries]
        species_ids = {entry.species_id for entry in entries}
        genus_ids = {entry.species.genus_id for entry in entries}
        family_ids = {entry.species.genus.family_id for entry in entries}
        cover = self._selected_trip_observation(observations, trip.cover_observation_id)
        location_links = sorted(trip.location_links, key=lambda item: item.visit_order)
        locations = (
            [
                {
                    "id": link.location.id,
                    "catalog_number": link.location.catalog_number,
                    "name": link.location.name,
                    "visit_order": link.visit_order,
                    "is_primary": link.is_primary,
                }
                for link in location_links
            ]
            if location_links
            else [
                {
                    "id": trip.location.id,
                    "catalog_number": trip.location.catalog_number,
                    "name": trip.location.name,
                    "visit_order": 1,
                    "is_primary": True,
                }
            ]
        )
        return {
            "id": trip.id,
            "catalog_number": trip.catalog_number,
            "name": trip.name or trip.location.name,
            "custom_name": trip.name,
            "location": {
                "id": trip.location.id,
                "catalog_number": trip.location.catalog_number,
                "name": trip.location.name,
            },
            "locations": locations,
            "location_count": len(locations),
            "started_at": trip.started_at.isoformat(timespec="minutes"),
            "ended_at": trip.ended_at.isoformat(timespec="minutes"),
            "duration_minutes": int((trip.ended_at - trip.started_at).total_seconds() / 60),
            "notes": trip.notes,
            "observation_count": len(observations),
            "species_count": len(species_ids),
            "genus_count": len(genus_ids),
            "family_count": len(family_ids),
            "cover_observation_id": cover.id if cover else None,
            "cover_url": self._media_url(cover.photo_asset, thumbnail=True) if cover else None,
        }

    @staticmethod
    def _selected_trip_observation(
        observations: list[Observation], selected_id: int | None
    ) -> Observation | None:
        if selected_id is not None:
            selected = next((item for item in observations if item.id == selected_id), None)
            if selected is not None:
                return selected
        return min(observations, key=lambda item: (item.observed_at, item.id), default=None)

    def set_location_observations(
        self, location_id: int, payload: LocationObservationSelectionInput
    ) -> dict:
        location = self.session.get(BirdingLocation, location_id)
        if location is None:
            raise DomainError("观鸟地点不存在", 404)
        selected_ids = set(payload.observation_ids)
        observations = self.session.scalars(
            select(Observation)
            .where(Observation.id.in_(selected_ids))
            .options(selectinload(Observation.location_link))
        ).all() if selected_ids else []
        if len(observations) != len(selected_ids):
            raise DomainError("所选观察记录中存在无效记录", 422)
        self.session.execute(
            delete(ObservationLocationLink).where(
                ObservationLocationLink.location_id == location_id,
                ObservationLocationLink.observation_id.not_in(selected_ids),
            )
        )
        for observation in observations:
            if observation.location_link is None:
                observation.location_link = ObservationLocationLink(location_id=location_id)
            else:
                observation.location_link.location_id = location_id
        self.session.commit()
        self.session.expire_all()
        return self.location_detail(location_id)

    def delete_location(self, location_id: int) -> dict:
        location = self.session.scalar(
            select(BirdingLocation)
            .where(BirdingLocation.id == location_id)
            .options(
                selectinload(BirdingLocation.observation_links),
                selectinload(BirdingLocation.cover),
            )
        )
        if location is None:
            raise DomainError("观鸟地点不存在", 404)
        if self.session.scalar(
            select(func.count(TripLocation.id)).where(TripLocation.location_id == location_id)
        ):
            raise DomainError("该地点仍有关联的观鸟行程，请先删除行程", 409)
        unlinked_count = len(location.observation_links)
        cover_asset_id = location.cover.asset_id if location.cover else None
        self.session.delete(location)
        self.session.commit()
        if cover_asset_id is not None:
            self._remove_unreferenced_assets({cover_asset_id})
        return {"deleted_location_id": location_id, "unlinked_observation_count": unlinked_count}

    def _location_summary(self, location: BirdingLocation) -> dict:
        observations = sorted(
            (link.observation for link in location.observation_links),
            key=lambda item: (item.observed_at, item.id),
        )
        visit_days = {item.observed_at.date() for item in observations}
        species_ids = {
            entry.species_id for item in observations for entry in item.species_entries
        }
        fallback_cover = observations[-1] if observations else None
        custom_cover_asset = location.cover.asset if location.cover else None
        return {
            "id": location.id,
            "catalog_number": location.catalog_number,
            "name": location.name,
            "location_type": location.location_type.value,
            "country_code": location.country_code,
            "country_name": location.country_name,
            "admin1_code": location.admin1_code,
            "admin1_name": location.admin1_name,
            "city": location.city,
            "district": location.district,
            "center_latitude": location.center_latitude,
            "center_longitude": location.center_longitude,
            "coordinate_system": location.coordinate_system,
            "radius_meters": location.radius_meters,
            "notes": location.notes,
            "observation_count": len(observations),
            "species_count": len(species_ids),
            "visit_day_count": len(visit_days),
            "trip_count": len(location.trip_links) or len(location.trips),
            "first_observed_at": (
                observations[0].observed_at.isoformat(timespec="minutes")
                if observations
                else None
            ),
            "last_observed_at": (
                observations[-1].observed_at.isoformat(timespec="minutes")
                if observations
                else None
            ),
            "cover_url": (
                self._media_url(custom_cover_asset, thumbnail=True)
                if custom_cover_asset is not None
                else (
                    self._media_url(fallback_cover.photo_asset, thumbnail=True)
                    if fallback_cover
                    else None
                )
            ),
            "cover_source": (
                "custom"
                if custom_cover_asset is not None
                else ("observation" if fallback_cover else None)
            ),
        }

    def list_observations(self) -> list[dict]:
        observations = self.session.scalars(
            select(Observation)
            .options(
                selectinload(Observation.species),
                selectinload(Observation.subspecies),
                selectinload(Observation.photo_asset),
                selectinload(Observation.audio_links).selectinload(ObservationAudio.asset),
                selectinload(Observation.location_link).selectinload(
                    ObservationLocationLink.location
                ),
                selectinload(Observation.trip_link)
                .selectinload(ObservationTripLink.trip)
                .selectinload(BirdingTrip.location),
            )
            .order_by(Observation.observed_at.desc(), Observation.id.desc())
        ).all()
        return [self._observation_dict(item) for item in observations]

    def homepage_feature(self) -> dict:
        preference = self.session.get(HomeDisplayPreference, 1)
        selected_id = preference.featured_observation_id if preference else None
        observation = None
        if selected_id is not None:
            observation = self._homepage_observation_query().where(
                Observation.id == selected_id
            )
            observation = self.session.scalar(observation)

        selection_mode = "manual" if observation is not None else "latest"
        if observation is None:
            observation = self.session.scalar(
                self._homepage_observation_query().order_by(
                    Observation.observed_at.desc(), Observation.id.desc()
                )
            )

        return {
            "selection_mode": selection_mode,
            "observation": self._observation_dict(observation) if observation else None,
        }

    def set_homepage_feature(self, observation_id: int | None) -> dict:
        preference = self.session.get(HomeDisplayPreference, 1)
        if preference is None:
            preference = HomeDisplayPreference(id=1)
            self.session.add(preference)

        if observation_id is not None:
            observation = self.session.get(Observation, observation_id)
            if observation is None:
                raise DomainError("观察记录不存在", 404)

        preference.featured_observation_id = observation_id
        self.session.commit()
        return self.homepage_feature()

    @staticmethod
    def _homepage_observation_query():
        return select(Observation).options(
            selectinload(Observation.species),
            selectinload(Observation.subspecies),
            selectinload(Observation.photo_asset),
            selectinload(Observation.audio_links).selectinload(ObservationAudio.asset),
            selectinload(Observation.location_link).selectinload(
                ObservationLocationLink.location
            ),
            selectinload(Observation.trip_link)
            .selectinload(ObservationTripLink.trip)
            .selectinload(BirdingTrip.location),
        )

    def update_observation(
        self, observation_id: int, payload: ObservationUpdateInput
    ) -> dict:
        observation = self.session.scalar(
            select(Observation)
            .where(Observation.id == observation_id)
            .options(
                selectinload(Observation.species),
                selectinload(Observation.subspecies),
                selectinload(Observation.photo_asset),
                selectinload(Observation.audio_links).selectinload(ObservationAudio.asset),
                selectinload(Observation.location_link).selectinload(
                    ObservationLocationLink.location
                ),
                selectinload(Observation.trip_link)
                .selectinload(ObservationTripLink.trip)
                .selectinload(BirdingTrip.location),
            )
        )
        if observation is None:
            raise DomainError("观察记录不存在", 404)

        entry = next((item for item in observation.species_entries if item.is_primary), None)

        if observation.photo_type is PhotoType.GROUP:
            if any(
                value is not None
                for value in (payload.sex, payload.life_stage, payload.subspecies_id)
            ):
                raise DomainError("群体照片只能修改备注", 422)
        else:
            if payload.sex is None or payload.life_stage is None:
                raise DomainError("个体照片必须保留性别和生命阶段", 422)
            selected_subspecies = None
            if payload.subspecies_id is not None:
                selected_subspecies = self.session.get(Subspecies, payload.subspecies_id)
                if (
                    selected_subspecies is None
                    or selected_subspecies.species_id != observation.species_id
                ):
                    raise DomainError("所选亚种不属于该观察记录的物种", 422)
            observation.sex = payload.sex
            observation.life_stage = payload.life_stage
            observation.subspecies = selected_subspecies
            if entry is not None:
                entry.sex = payload.sex
                entry.life_stage = payload.life_stage
                entry.subspecies = selected_subspecies

        observation.notes = payload.notes or None
        self.session.commit()
        return self._observation_dict(observation)

    def update_observation_species(
        self,
        observation_id: int,
        entry_id: int,
        payload: ObservationUpdateInput,
    ) -> dict:
        entry = self.session.scalar(
            select(ObservationSpecies).where(
                ObservationSpecies.id == entry_id,
                ObservationSpecies.observation_id == observation_id,
            )
        )
        if entry is None:
            raise DomainError("观察中的物种条目不存在", 404)
        if entry.photo_type is PhotoType.GROUP:
            if any(
                value is not None
                for value in (payload.sex, payload.life_stage, payload.subspecies_id)
            ):
                raise DomainError("群体照片只能修改物种备注", 422)
        else:
            if payload.sex is None or payload.life_stage is None:
                raise DomainError("个体照片必须保留性别和生命阶段", 422)
            selected_subspecies = None
            if payload.subspecies_id is not None:
                selected_subspecies = self.session.get(Subspecies, payload.subspecies_id)
                if (
                    selected_subspecies is None
                    or selected_subspecies.species_id != entry.species_id
                ):
                    raise DomainError("所选亚种不属于该物种", 422)
            entry.sex = payload.sex
            entry.life_stage = payload.life_stage
            entry.subspecies = selected_subspecies
        entry.notes = payload.notes or None
        if entry.is_primary:
            entry.observation.sex = entry.sex
            entry.observation.life_stage = entry.life_stage
            entry.observation.subspecies = entry.subspecies
        self.session.commit()
        return self._observation_dict(entry.observation)

    def add_observation_species(
        self, observation_id: int, payload: ObservationSpeciesInput
    ) -> dict:
        observation = self.session.scalar(
            select(Observation)
            .where(Observation.id == observation_id)
            .options(selectinload(Observation.species_entries))
        )
        if observation is None:
            raise DomainError("观察记录不存在", 404)
        if len(observation.species_entries) >= 10:
            raise DomainError("一笔观察最多记录 10 个物种", 422)
        if any(entry.species_id == payload.species_id for entry in observation.species_entries):
            raise DomainError("这笔观察已经记录了该物种", 422)
        species = self.session.get(Species, payload.species_id)
        if species is None:
            raise DomainError("物种不存在", 404)
        subspecies = None
        if payload.subspecies_id is not None:
            subspecies = self.session.get(Subspecies, payload.subspecies_id)
            if subspecies is None or subspecies.species_id != species.id:
                raise DomainError("所选亚种不属于该物种", 422)
        observation.species_entries.append(
            ObservationSpecies(
                species=species,
                subspecies=subspecies,
                photo_type=payload.photo_type,
                sex=payload.sex,
                life_stage=payload.life_stage,
                notes=payload.notes or None,
                is_primary=False,
            )
        )
        self.session.commit()
        return self._observation_dict(observation)

    def delete_observation_species(self, observation_id: int, entry_id: int) -> dict:
        entry = self.session.scalar(
            select(ObservationSpecies)
            .where(
                ObservationSpecies.id == entry_id,
                ObservationSpecies.observation_id == observation_id,
            )
            .options(
                selectinload(ObservationSpecies.species)
                .selectinload(Species.genus)
                .selectinload(Genus.family)
                .selectinload(Family.order),
                selectinload(ObservationSpecies.species)
                .selectinload(Species.audio_links)
                .selectinload(SpeciesAudio.asset),
            )
        )
        if entry is None:
            raise DomainError("观察中的物种条目不存在", 404)
        observation = entry.observation
        if len(observation.species_entries) <= 1:
            raise DomainError("一笔观察必须至少保留一个物种", 422)
        if entry.is_primary:
            replacement = next(
                item for item in observation.species_entries if item.id != entry.id
            )
            replacement.is_primary = True
            observation.species = replacement.species
            observation.photo_type = replacement.photo_type
            observation.sex = replacement.sex
            observation.life_stage = replacement.life_stage
            observation.subspecies = replacement.subspecies
        species = entry.species
        self.session.delete(entry)
        self.session.flush()
        remaining = self.session.scalar(
            select(func.count(ObservationSpecies.id)).where(
                ObservationSpecies.species_id == species.id
            )
        )
        removed_species = not remaining
        asset_ids: set[int] = set()
        if removed_species:
            asset_ids.update(link.asset_id for link in species.audio_links)
            genus_id = species.genus_id
            family_id = species.genus.family_id
            order_id = species.genus.family.order_id
            self.session.delete(species)
            self.session.flush()
            self._prune_taxonomy(genus_id, family_id, order_id)
        self.session.commit()
        if asset_ids:
            self._remove_unreferenced_assets(asset_ids)
        return {
            "deleted_entry_id": entry_id,
            "removed_species": removed_species,
        }

    def _observation_dict(self, item: Observation, species_id: int | None = None) -> dict:
        entries = sorted(item.species_entries, key=lambda value: (not value.is_primary, value.id))
        if not entries:
            entries = [
                ObservationSpecies(
                    id=0,
                    observation_id=item.id,
                    species=item.species,
                    subspecies=item.subspecies,
                    photo_type=item.photo_type,
                    sex=item.sex,
                    life_stage=item.life_stage,
                    is_primary=True,
                )
            ]
        focused_entry = next(
            (entry for entry in entries if (entry.species_id or entry.species.id) == species_id),
            entries[0],
        )
        return {
            "id": item.id,
            "species_id": focused_entry.species_id or focused_entry.species.id,
            "species_name": focused_entry.species.chinese_name,
            "species_scientific_name": focused_entry.species.scientific_name,
            "catalog_number": focused_entry.species.catalog_number,
            "location": (
                {
                    "id": item.location_link.location.id,
                    "catalog_number": item.location_link.location.catalog_number,
                    "name": item.location_link.location.name,
                }
                if item.location_link
                else None
            ),
            "trip": (
                {
                    "id": item.trip_link.trip.id,
                    "catalog_number": item.trip_link.trip.catalog_number,
                    "name": item.trip_link.trip.name
                    or item.trip_link.trip.location.name,
                    "started_at": item.trip_link.trip.started_at.isoformat(
                        timespec="minutes"
                    ),
                    "ended_at": item.trip_link.trip.ended_at.isoformat(timespec="minutes"),
                    "location_name": item.trip_link.trip.location.name,
                }
                if item.trip_link
                else None
            ),
            "observed_at": item.observed_at.isoformat(timespec="minutes"),
            "latitude": item.latitude,
            "longitude": item.longitude,
            "country_code": item.country_code,
            "country_name": item.country_name,
            "admin1_code": item.admin1_code,
            "admin1_name": item.admin1_name,
            "locality": item.locality,
            "season": item.season.value,
            "season_note": item.season_note,
            "photo_type": focused_entry.photo_type.value,
            "sex": focused_entry.sex.value if focused_entry.sex else None,
            "life_stage": focused_entry.life_stage.value if focused_entry.life_stage else None,
            "subspecies": (
                {
                    "id": focused_entry.subspecies.id,
                    "chinese_name": focused_entry.subspecies.chinese_name,
                    "scientific_name": focused_entry.subspecies.scientific_name,
                }
                if focused_entry.subspecies
                else None
            ),
            "notes": item.notes,
            "species_count": len(entries),
            "species_entries": [
                {
                    "id": entry.id,
                    "species_id": entry.species_id or entry.species.id,
                    "catalog_number": entry.species.catalog_number,
                    "species_name": entry.species.chinese_name,
                    "species_scientific_name": entry.species.scientific_name,
                    "photo_type": entry.photo_type.value,
                    "sex": entry.sex.value if entry.sex else None,
                    "life_stage": entry.life_stage.value if entry.life_stage else None,
                    "subspecies": (
                        {
                            "id": entry.subspecies.id,
                            "chinese_name": entry.subspecies.chinese_name,
                            "scientific_name": entry.subspecies.scientific_name,
                        }
                        if entry.subspecies
                        else None
                    ),
                    "notes": entry.notes,
                    "is_primary": entry.is_primary,
                }
                for entry in entries
            ],
            "photo_asset_id": item.photo_asset_id,
            "photo_url": self._media_url(item.photo_asset),
            "thumbnail_url": self._media_url(item.photo_asset, thumbnail=True),
            "audio": [
                {
                    "id": link.id,
                    "asset_id": link.asset_id,
                    "url": self._media_url(link.asset),
                }
                for link in item.audio_links
            ],
        }

    @staticmethod
    def _proof(observation: Observation) -> dict:
        return {
            "observation_id": observation.id,
            "asset_id": observation.photo_asset_id,
            "photo_url": BirdService._media_url(observation.photo_asset),
            "thumbnail_url": BirdService._media_url(
                observation.photo_asset, thumbnail=True
            ),
        }

    @staticmethod
    def _media_url(asset: MediaAsset, thumbnail: bool = False) -> str:
        thumbnail_query = "thumbnail=true&" if thumbnail else ""
        return f"/api/media/{asset.id}?{thumbnail_query}v={asset.sha256[:16]}"

    def _selected_archive_proof(
        self,
        fallback: dict,
        selections: dict[tuple[EvidenceDimension, str], int],
        dimension: EvidenceDimension,
        value_key: str,
        observations_by_id: dict[int, Observation],
        species_id: int,
    ) -> dict:
        selected_id = selections.get((dimension, value_key))
        selected = observations_by_id.get(selected_id) if selected_id else None
        if selected is not None and self._observation_matches_archive(
            selected, dimension, value_key, species_id
        ):
            return self._proof(selected)
        return fallback

    @staticmethod
    def _observation_matches_archive(
        observation: Observation,
        dimension: EvidenceDimension,
        value_key: str,
        species_id: int,
    ) -> bool:
        entry = next(
            (item for item in observation.species_entries if item.species_id == species_id),
            None,
        )
        if entry is None:
            return False
        if dimension is EvidenceDimension.SEX:
            return entry.sex is not None and entry.sex.value == value_key
        if dimension is EvidenceDimension.LIFE_STAGE:
            return (
                entry.life_stage is not None
                and entry.life_stage.value == value_key
            )
        if dimension is EvidenceDimension.SUBSPECIES:
            return (
                entry.subspecies_id is not None
                and str(entry.subspecies_id) == value_key
            )
        return False

    @staticmethod
    def _selected_observation(
        observations: list[Observation], selected_id: int | None
    ) -> Observation:
        if selected_id is not None:
            selected = next((item for item in observations if item.id == selected_id), None)
            if selected is not None:
                return selected
        return observations[0]

    def delete_observation(self, observation_id: int) -> dict:
        observation = self.session.scalar(
            select(Observation)
            .where(Observation.id == observation_id)
            .options(
                selectinload(Observation.audio_links),
                selectinload(Observation.species_entries)
                .selectinload(ObservationSpecies.species)
                .selectinload(Species.audio_links)
                .selectinload(SpeciesAudio.asset),
                selectinload(Observation.species_entries)
                .selectinload(ObservationSpecies.species)
                .selectinload(Species.genus)
                .selectinload(Genus.family)
                .selectinload(Family.order),
            )
        )
        if observation is None:
            raise DomainError("观察记录不存在", 404)

        asset_ids = {observation.photo_asset_id}
        asset_ids.update(link.asset_id for link in observation.audio_links)
        species_to_remove = []
        for entry in observation.species_entries:
            count = self.session.scalar(
                select(func.count(ObservationSpecies.id)).where(
                    ObservationSpecies.species_id == entry.species_id
                )
            )
            if count == 1:
                species_to_remove.append(entry.species)
                asset_ids.update(link.asset_id for link in entry.species.audio_links)

        self.session.execute(delete(Observation).where(Observation.id == observation_id))
        self.session.flush()
        removed_species_ids = []
        for species in species_to_remove:
            asset_ids.update(link.asset_id for link in species.audio_links)
            genus_id = species.genus_id
            family_id = species.genus.family_id
            order_id = species.genus.family.order_id
            self.session.execute(delete(Species).where(Species.id == species.id))
            self.session.flush()
            removed_species_ids.append(species.id)
            self._prune_taxonomy(genus_id, family_id, order_id)

        self.session.commit()
        self._remove_unreferenced_assets(asset_ids)
        return {
            "deleted_observation_id": observation_id,
            "removed_species": bool(removed_species_ids),
            "removed_species_ids": removed_species_ids,
        }

    def _prune_taxonomy(self, genus_id: int, family_id: int, order_id: int) -> None:
        if not self.session.scalar(
            select(func.count(Species.id)).where(Species.genus_id == genus_id)
        ):
            self.session.execute(delete(Genus).where(Genus.id == genus_id))
            self.session.flush()
        if not self.session.scalar(
            select(func.count(Genus.id)).where(Genus.family_id == family_id)
        ):
            self.session.execute(delete(Family).where(Family.id == family_id))
            self.session.flush()
        if not self.session.scalar(
            select(func.count(Family.id)).where(Family.order_id == order_id)
        ):
            self.session.execute(delete(TaxonomicOrder).where(TaxonomicOrder.id == order_id))

    def _remove_unreferenced_assets(self, asset_ids: set[int]) -> None:
        files_to_remove: list[MediaAsset] = []
        for asset_id in asset_ids:
            references = sum(
                int(value or 0)
                for value in (
                    self.session.scalar(
                        select(func.count(Observation.id)).where(
                            Observation.photo_asset_id == asset_id
                        )
                    ),
                    self.session.scalar(
                        select(func.count(ObservationAudio.id)).where(
                            ObservationAudio.asset_id == asset_id
                        )
                    ),
                    self.session.scalar(
                        select(func.count(SpeciesAudio.id)).where(SpeciesAudio.asset_id == asset_id)
                    ),
                    self.session.scalar(
                        select(func.count(LocationCover.location_id)).where(
                            LocationCover.asset_id == asset_id
                        )
                    ),
                )
            )
            if references == 0:
                asset = self.session.get(MediaAsset, asset_id)
                if asset is not None:
                    files_to_remove.append(asset)
                    self.session.delete(asset)
        self.session.commit()
        for asset in files_to_remove:
            self.media_store.remove_files(asset)

    def stats(self) -> dict:
        return {
            "species_count": self.session.scalar(select(func.count(Species.id))) or 0,
            "observation_count": self.session.scalar(select(func.count(Observation.id))) or 0,
            "photo_count": self.session.scalar(
                select(func.count(MediaAsset.id)).where(MediaAsset.kind == MediaKind.PHOTO)
            )
            or 0,
            "audio_count": self.session.scalar(
                select(func.count(MediaAsset.id)).where(MediaAsset.kind == MediaKind.AUDIO)
            )
            or 0,
        }
