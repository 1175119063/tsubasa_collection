from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.orm import selectinload

from .enums import EvidenceDimension, PhotoType
from .models import (
    BirdingTrip,
    CollectionPlan,
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
    Subspecies,
    TaxonomicOrder,
)
from .schemas import ObservationSpeciesInput, ObservationUpdateInput
from .service_common import DomainError


class ObservationServiceMixin:
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
            "photo_url": ObservationServiceMixin._media_url(observation.photo_asset),
            "thumbnail_url": ObservationServiceMixin._media_url(
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
                    self.session.scalar(
                        select(func.count(CollectionPlan.id)).where(
                            CollectionPlan.logo_asset_id == asset_id
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

