from __future__ import annotations

from fastapi import UploadFile
from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from .enums import BodySize, EcologicalGroup, EvidenceDimension, LifeStage, Sex
from .media_store import ImportedMedia
from .models import (
    BirdingTrip,
    EvidenceSelection,
    Family,
    Genus,
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
    TaxonomicOrder,
)
from .schemas import SpeciesAudioInput, SpeciesProfileUpdateInput
from .service_common import DomainError, normalized_name


class SpeciesServiceMixin:
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

    def delete_species_audio(self, species_id: int, audio_id: int) -> dict:
        link = self.session.scalar(
            select(SpeciesAudio).where(
                SpeciesAudio.id == audio_id,
                SpeciesAudio.species_id == species_id,
            )
        )
        if link is None:
            raise DomainError("物种录音不存在", 404)
        asset_id = link.asset_id
        self.session.delete(link)
        self.session.flush()
        self._remove_unreferenced_assets({asset_id})
        self.session.commit()
        return {"deleted": True, "audio_id": audio_id}

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
            raise DomainError("个体标签不能重复", 422)
        for individual in payload.individuals:
            if (
                individual.observation_id is not None
                and individual.observation_id not in observations_by_id
            ):
                raise DomainError("个体标签只能关联该物种的观察记录", 422)

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
