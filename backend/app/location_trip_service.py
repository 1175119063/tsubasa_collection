from __future__ import annotations

from collections import defaultdict

from fastapi import UploadFile
from sqlalchemy import delete, func, select
from sqlalchemy.orm import selectinload

from .media_store import ImportedMedia
from .models import (
    BirdingLocation,
    BirdingTrip,
    Genus,
    LocationCover,
    Observation,
    ObservationAudio,
    ObservationLocationLink,
    ObservationTripLink,
    Species,
    TripLocation,
)
from .schemas import (
    LocationInput,
    LocationObservationSelectionInput,
    TripInput,
    TripObservationSelectionInput,
)
from .service_common import DomainError, normalized_name


class LocationTripServiceMixin:
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

