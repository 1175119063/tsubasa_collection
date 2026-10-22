from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base
from .enums import (
    BodySize,
    ChinaProtectionStatus,
    EcologicalGroup,
    EvidenceDimension,
    HabitatType,
    IUCNStatus,
    LifeStage,
    LocationType,
    MediaKind,
    PhotoType,
    Season,
    Sex,
)


def utc_now() -> datetime:
    return datetime.now(UTC)


def enum_type(enum_class, name: str) -> SAEnum:
    return SAEnum(
        enum_class,
        name=name,
        native_enum=False,
        values_callable=lambda members: [member.value for member in members],
        validate_strings=True,
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class TaxonomicOrder(TimestampMixin, Base):
    __tablename__ = "taxonomic_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chinese_name: Mapped[str] = mapped_column(String(120))
    scientific_name: Mapped[str] = mapped_column(String(120))
    scientific_name_key: Mapped[str] = mapped_column(String(120), unique=True, index=True)

    families: Mapped[list[Family]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class Family(TimestampMixin, Base):
    __tablename__ = "families"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("taxonomic_orders.id", ondelete="CASCADE"), index=True
    )
    chinese_name: Mapped[str] = mapped_column(String(120))
    scientific_name: Mapped[str] = mapped_column(String(120))
    scientific_name_key: Mapped[str] = mapped_column(String(120), unique=True, index=True)

    order: Mapped[TaxonomicOrder] = relationship(back_populates="families")
    genera: Mapped[list[Genus]] = relationship(
        back_populates="family", cascade="all, delete-orphan"
    )


class Genus(TimestampMixin, Base):
    __tablename__ = "genera"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    family_id: Mapped[int] = mapped_column(
        ForeignKey("families.id", ondelete="CASCADE"), index=True
    )
    chinese_name: Mapped[str] = mapped_column(String(120))
    scientific_name: Mapped[str] = mapped_column(String(120))
    scientific_name_key: Mapped[str] = mapped_column(String(120), unique=True, index=True)

    family: Mapped[Family] = relationship(back_populates="genera")
    species: Mapped[list[Species]] = relationship(
        back_populates="genus", cascade="all, delete-orphan"
    )


class Species(TimestampMixin, Base):
    __tablename__ = "species"
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    genus_id: Mapped[int] = mapped_column(ForeignKey("genera.id", ondelete="CASCADE"), index=True)
    chinese_name: Mapped[str] = mapped_column(String(120))
    scientific_name: Mapped[str] = mapped_column(String(180))
    scientific_name_key: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    iucn_status: Mapped[IUCNStatus] = mapped_column(enum_type(IUCNStatus, "iucn_status"))
    china_protection_status: Mapped[ChinaProtectionStatus | None] = mapped_column(
        enum_type(ChinaProtectionStatus, "china_protection_status"), nullable=True
    )
    has_subspecies: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    genus: Mapped[Genus] = relationship(back_populates="species")
    subspecies: Mapped[list[Subspecies]] = relationship(
        back_populates="species", cascade="all, delete-orphan"
    )
    observations: Mapped[list[Observation]] = relationship(
        back_populates="species", cascade="all, delete-orphan"
    )
    observation_entries: Mapped[list[ObservationSpecies]] = relationship(
        back_populates="species", cascade="all, delete-orphan"
    )
    audio_links: Mapped[list[SpeciesAudio]] = relationship(
        back_populates="species", cascade="all, delete-orphan"
    )
    display_preference: Mapped[SpeciesDisplayPreference | None] = relationship(
        back_populates="species", cascade="all, delete-orphan", uselist=False
    )
    evidence_selections: Mapped[list[EvidenceSelection]] = relationship(
        back_populates="species", cascade="all, delete-orphan"
    )
    behavior_tags: Mapped[list[SpeciesBehaviorTag]] = relationship(
        back_populates="species", cascade="all, delete-orphan"
    )
    individual_tags: Mapped[list[SpeciesIndividualTag]] = relationship(
        back_populates="species", cascade="all, delete-orphan"
    )
    ecology_profile: Mapped[SpeciesEcologyProfile | None] = relationship(
        back_populates="species", cascade="all, delete-orphan", uselist=False
    )
    habitat_preferences: Mapped[list[SpeciesHabitatPreference]] = relationship(
        back_populates="species", cascade="all, delete-orphan"
    )
    collection_memberships: Mapped[list[CollectionPlanSpecies]] = relationship(
        back_populates="species", cascade="all, delete-orphan"
    )

    @property
    def catalog_number(self) -> str:
        return f"AV-{self.id:06d}"


class Subspecies(TimestampMixin, Base):
    __tablename__ = "subspecies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    species_id: Mapped[int] = mapped_column(
        ForeignKey("species.id", ondelete="CASCADE"), index=True
    )
    chinese_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    scientific_name: Mapped[str] = mapped_column(String(220))
    scientific_name_key: Mapped[str] = mapped_column(String(220), unique=True, index=True)

    species: Mapped[Species] = relationship(back_populates="subspecies")
    observations: Mapped[list[Observation]] = relationship(back_populates="subspecies")


class MediaAsset(TimestampMixin, Base):
    __tablename__ = "media_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[MediaKind] = mapped_column(enum_type(MediaKind, "media_kind"))
    sha256: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    relative_path: Mapped[str] = mapped_column(String(500), unique=True)
    thumbnail_relative_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(80))
    byte_size: Mapped[int] = mapped_column(BigInteger)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)


class Observation(TimestampMixin, Base):
    __tablename__ = "observations"
    __table_args__ = (
        CheckConstraint("latitude >= -90 AND latitude <= 90", name="latitude_range"),
        CheckConstraint("longitude >= -180 AND longitude <= 180", name="longitude_range"),
        CheckConstraint(
            "(photo_type = 'group' AND sex IS NULL AND life_stage IS NULL "
            "AND subspecies_id IS NULL) OR "
            "(photo_type = 'individual' AND sex IS NOT NULL AND life_stage IS NOT NULL)",
            name="photo_subject_fields",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    species_id: Mapped[int] = mapped_column(
        ForeignKey("species.id", ondelete="CASCADE"), index=True
    )
    subspecies_id: Mapped[int | None] = mapped_column(
        ForeignKey("subspecies.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    photo_asset_id: Mapped[int] = mapped_column(
        ForeignKey("media_assets.id", ondelete="RESTRICT"), index=True
    )
    photo_type: Mapped[PhotoType] = mapped_column(enum_type(PhotoType, "photo_type"))
    observed_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    country_code: Mapped[str] = mapped_column(String(8), index=True)
    country_name: Mapped[str] = mapped_column(String(120))
    admin1_code: Mapped[str] = mapped_column(String(40), index=True)
    admin1_name: Mapped[str] = mapped_column(String(120))
    locality: Mapped[str] = mapped_column(String(240))
    season: Mapped[Season] = mapped_column(enum_type(Season, "season"), index=True)
    season_note: Mapped[str | None] = mapped_column(String(120), nullable=True)
    sex: Mapped[Sex | None] = mapped_column(enum_type(Sex, "sex"), nullable=True)
    life_stage: Mapped[LifeStage | None] = mapped_column(
        enum_type(LifeStage, "life_stage"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    species: Mapped[Species] = relationship(back_populates="observations")
    subspecies: Mapped[Subspecies | None] = relationship(back_populates="observations")
    photo_asset: Mapped[MediaAsset] = relationship(foreign_keys=[photo_asset_id])
    audio_links: Mapped[list[ObservationAudio]] = relationship(
        back_populates="observation", cascade="all, delete-orphan"
    )
    location_link: Mapped[ObservationLocationLink | None] = relationship(
        back_populates="observation", cascade="all, delete-orphan", uselist=False
    )
    trip_link: Mapped[ObservationTripLink | None] = relationship(
        back_populates="observation", cascade="all, delete-orphan", uselist=False
    )
    species_entries: Mapped[list[ObservationSpecies]] = relationship(
        back_populates="observation", cascade="all, delete-orphan"
    )
    photos: Mapped[list[ObservationPhoto]] = relationship(
        back_populates="observation",
        cascade="all, delete-orphan",
        order_by="ObservationPhoto.position",
    )


class ObservationSpecies(TimestampMixin, Base):
    __tablename__ = "observation_species"
    __table_args__ = (
        UniqueConstraint("observation_id", "species_id"),
        CheckConstraint(
            "(photo_type = 'group' AND sex IS NULL AND life_stage IS NULL "
            "AND subspecies_id IS NULL) OR "
            "(photo_type = 'individual' AND sex IS NOT NULL AND life_stage IS NOT NULL)",
            name="subject_fields",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    observation_id: Mapped[int] = mapped_column(
        ForeignKey("observations.id", ondelete="CASCADE"), index=True
    )
    species_id: Mapped[int] = mapped_column(
        ForeignKey("species.id", ondelete="CASCADE"), index=True
    )
    subspecies_id: Mapped[int | None] = mapped_column(
        ForeignKey("subspecies.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    photo_type: Mapped[PhotoType] = mapped_column(enum_type(PhotoType, "entry_photo_type"))
    sex: Mapped[Sex | None] = mapped_column(enum_type(Sex, "entry_sex"), nullable=True)
    life_stage: Mapped[LifeStage | None] = mapped_column(
        enum_type(LifeStage, "entry_life_stage"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    observation: Mapped[Observation] = relationship(back_populates="species_entries")
    species: Mapped[Species] = relationship(back_populates="observation_entries")
    subspecies: Mapped[Subspecies | None] = relationship()
    behavior_links: Mapped[list[ObservationBehavior]] = relationship(
        back_populates="entry", cascade="all, delete-orphan", lazy="selectin"
    )
    photo_links: Mapped[list[ObservationPhotoSpecies]] = relationship(
        back_populates="species_entry", cascade="all, delete-orphan"
    )


class ObservationPhoto(TimestampMixin, Base):
    __tablename__ = "observation_photos"
    __table_args__ = (
        UniqueConstraint("observation_id", "asset_id"),
        CheckConstraint("position >= 0", name="observation_photo_position"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    observation_id: Mapped[int] = mapped_column(
        ForeignKey("observations.id", ondelete="CASCADE"), index=True
    )
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("media_assets.id", ondelete="RESTRICT"), index=True
    )
    observed_at: Mapped[datetime] = mapped_column(DateTime)
    position: Mapped[int] = mapped_column(Integer, default=0)
    is_cover: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    observation: Mapped[Observation] = relationship(back_populates="photos")
    asset: Mapped[MediaAsset] = relationship()
    species_links: Mapped[list[ObservationPhotoSpecies]] = relationship(
        back_populates="photo", cascade="all, delete-orphan"
    )


class ObservationPhotoSpecies(TimestampMixin, Base):
    __tablename__ = "observation_photo_species"

    photo_id: Mapped[int] = mapped_column(
        ForeignKey("observation_photos.id", ondelete="CASCADE"), primary_key=True
    )
    observation_species_id: Mapped[int] = mapped_column(
        ForeignKey("observation_species.id", ondelete="CASCADE"), primary_key=True
    )

    photo: Mapped[ObservationPhoto] = relationship(back_populates="species_links")
    species_entry: Mapped[ObservationSpecies] = relationship(back_populates="photo_links")


class BirdingLocation(TimestampMixin, Base):
    __tablename__ = "birding_locations"
    __table_args__ = (
        UniqueConstraint("country_code", "admin1_code", "name_key"),
        CheckConstraint(
            "center_latitude >= -90 AND center_latitude <= 90",
            name="center_latitude_range",
        ),
        CheckConstraint(
            "center_longitude >= -180 AND center_longitude <= 180",
            name="center_longitude_range",
        ),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(180))
    name_key: Mapped[str] = mapped_column(String(180), index=True)
    location_type: Mapped[LocationType] = mapped_column(
        enum_type(LocationType, "location_type")
    )
    country_code: Mapped[str] = mapped_column(String(8), index=True)
    country_name: Mapped[str] = mapped_column(String(120))
    admin1_code: Mapped[str] = mapped_column(String(40), index=True)
    admin1_name: Mapped[str] = mapped_column(String(120))
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    district: Mapped[str | None] = mapped_column(String(120), nullable=True)
    center_latitude: Mapped[float] = mapped_column(Float)
    center_longitude: Mapped[float] = mapped_column(Float)
    coordinate_system: Mapped[str] = mapped_column(String(12), default="wgs84")
    radius_meters: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    observation_links: Mapped[list[ObservationLocationLink]] = relationship(
        back_populates="location", cascade="all, delete-orphan"
    )
    cover: Mapped[LocationCover | None] = relationship(
        back_populates="location", cascade="all, delete-orphan", uselist=False
    )
    trips: Mapped[list[BirdingTrip]] = relationship(back_populates="location")
    trip_links: Mapped[list[TripLocation]] = relationship(
        back_populates="location", cascade="all, delete-orphan"
    )

    @property
    def catalog_number(self) -> str:
        return f"LOC-{self.id:06d}"


class ObservationLocationLink(TimestampMixin, Base):
    __tablename__ = "observation_location_links"

    observation_id: Mapped[int] = mapped_column(
        ForeignKey("observations.id", ondelete="CASCADE"), primary_key=True
    )
    location_id: Mapped[int] = mapped_column(
        ForeignKey("birding_locations.id", ondelete="CASCADE"), index=True
    )

    observation: Mapped[Observation] = relationship(back_populates="location_link")
    location: Mapped[BirdingLocation] = relationship(back_populates="observation_links")


class LocationCover(TimestampMixin, Base):
    __tablename__ = "location_covers"

    location_id: Mapped[int] = mapped_column(
        ForeignKey("birding_locations.id", ondelete="CASCADE"), primary_key=True
    )
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("media_assets.id", ondelete="RESTRICT"), index=True
    )

    location: Mapped[BirdingLocation] = relationship(back_populates="cover")
    asset: Mapped[MediaAsset] = relationship()


class BirdingTrip(TimestampMixin, Base):
    __tablename__ = "birding_trips"
    __table_args__ = (
        CheckConstraint("ended_at > started_at", name="trip_time_order"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    location_id: Mapped[int] = mapped_column(
        ForeignKey("birding_locations.id", ondelete="RESTRICT"), index=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    ended_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    cover_observation_id: Mapped[int | None] = mapped_column(
        ForeignKey("observations.id", ondelete="SET NULL"), nullable=True
    )

    location: Mapped[BirdingLocation] = relationship(back_populates="trips")
    observation_links: Mapped[list[ObservationTripLink]] = relationship(
        back_populates="trip", cascade="all, delete-orphan"
    )
    location_links: Mapped[list[TripLocation]] = relationship(
        back_populates="trip", cascade="all, delete-orphan"
    )
    cover_observation: Mapped[Observation | None] = relationship(
        foreign_keys=[cover_observation_id]
    )

    @property
    def catalog_number(self) -> str:
        return f"TRIP-{self.id:06d}"


class TripLocation(TimestampMixin, Base):
    __tablename__ = "trip_locations"
    __table_args__ = (UniqueConstraint("trip_id", "location_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trip_id: Mapped[int] = mapped_column(
        ForeignKey("birding_trips.id", ondelete="CASCADE"), index=True
    )
    location_id: Mapped[int] = mapped_column(
        ForeignKey("birding_locations.id", ondelete="RESTRICT"), index=True
    )
    visit_order: Mapped[int] = mapped_column(Integer)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    trip: Mapped[BirdingTrip] = relationship(back_populates="location_links")
    location: Mapped[BirdingLocation] = relationship(back_populates="trip_links")


class ObservationTripLink(TimestampMixin, Base):
    __tablename__ = "observation_trip_links"

    observation_id: Mapped[int] = mapped_column(
        ForeignKey("observations.id", ondelete="CASCADE"), primary_key=True
    )
    trip_id: Mapped[int] = mapped_column(
        ForeignKey("birding_trips.id", ondelete="CASCADE"), index=True
    )

    observation: Mapped[Observation] = relationship(back_populates="trip_link")
    trip: Mapped[BirdingTrip] = relationship(back_populates="observation_links")


class ObservationAudio(TimestampMixin, Base):
    __tablename__ = "observation_audio"
    __table_args__ = (UniqueConstraint("observation_id", "asset_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    observation_id: Mapped[int] = mapped_column(
        ForeignKey("observations.id", ondelete="CASCADE"), index=True
    )
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("media_assets.id", ondelete="RESTRICT"), index=True
    )
    title: Mapped[str | None] = mapped_column(String(160), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    observation: Mapped[Observation] = relationship(back_populates="audio_links")
    asset: Mapped[MediaAsset] = relationship()


class SpeciesAudio(TimestampMixin, Base):
    __tablename__ = "species_audio"
    __table_args__ = (UniqueConstraint("species_id", "asset_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    species_id: Mapped[int] = mapped_column(
        ForeignKey("species.id", ondelete="CASCADE"), index=True
    )
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("media_assets.id", ondelete="RESTRICT"), index=True
    )
    title: Mapped[str | None] = mapped_column(String(160), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    locality: Mapped[str | None] = mapped_column(String(240), nullable=True)

    species: Mapped[Species] = relationship(back_populates="audio_links")
    asset: Mapped[MediaAsset] = relationship()


class SpeciesDisplayPreference(TimestampMixin, Base):
    __tablename__ = "species_display_preferences"

    species_id: Mapped[int] = mapped_column(
        ForeignKey("species.id", ondelete="CASCADE"), primary_key=True
    )
    cover_observation_id: Mapped[int | None] = mapped_column(
        ForeignKey("observations.id", ondelete="SET NULL"), nullable=True
    )
    first_encounter_observation_id: Mapped[int | None] = mapped_column(
        ForeignKey("observations.id", ondelete="SET NULL"), nullable=True
    )

    species: Mapped[Species] = relationship(back_populates="display_preference")
    cover_observation: Mapped[Observation | None] = relationship(
        foreign_keys=[cover_observation_id]
    )
    first_encounter_observation: Mapped[Observation | None] = relationship(
        foreign_keys=[first_encounter_observation_id]
    )


class HomeDisplayPreference(TimestampMixin, Base):
    __tablename__ = "home_display_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    featured_observation_id: Mapped[int | None] = mapped_column(
        ForeignKey("observations.id", ondelete="SET NULL"), nullable=True
    )

    featured_observation: Mapped[Observation | None] = relationship()


class SpeciesEcologyProfile(TimestampMixin, Base):
    __tablename__ = "species_ecology_profiles"

    species_id: Mapped[int] = mapped_column(
        ForeignKey("species.id", ondelete="CASCADE"), primary_key=True
    )
    ecological_group: Mapped[EcologicalGroup] = mapped_column(
        enum_type(EcologicalGroup, "ecological_group"), default=EcologicalGroup.UNKNOWN
    )
    body_size: Mapped[BodySize] = mapped_column(
        enum_type(BodySize, "body_size"), default=BodySize.UNKNOWN
    )

    species: Mapped[Species] = relationship(back_populates="ecology_profile")


class SpeciesHabitatPreference(TimestampMixin, Base):
    __tablename__ = "species_habitat_preferences"

    species_id: Mapped[int] = mapped_column(
        ForeignKey("species.id", ondelete="CASCADE"), primary_key=True
    )
    habitat: Mapped[HabitatType] = mapped_column(
        enum_type(HabitatType, "habitat_type"), primary_key=True
    )

    species: Mapped[Species] = relationship(back_populates="habitat_preferences")


class EvidenceSelection(TimestampMixin, Base):
    __tablename__ = "evidence_selections"
    __table_args__ = (UniqueConstraint("species_id", "dimension", "value_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    species_id: Mapped[int] = mapped_column(
        ForeignKey("species.id", ondelete="CASCADE"), index=True
    )
    observation_id: Mapped[int] = mapped_column(
        ForeignKey("observations.id", ondelete="CASCADE"), index=True
    )
    dimension: Mapped[EvidenceDimension] = mapped_column(
        enum_type(EvidenceDimension, "evidence_dimension")
    )
    value_key: Mapped[str] = mapped_column(String(220))

    species: Mapped[Species] = relationship(back_populates="evidence_selections")
    observation: Mapped[Observation] = relationship()


class SpeciesBehaviorTag(TimestampMixin, Base):
    __tablename__ = "species_behavior_tags"
    __table_args__ = (
        UniqueConstraint("species_id", "label_key"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    species_id: Mapped[int] = mapped_column(
        ForeignKey("species.id", ondelete="CASCADE"), index=True
    )
    label: Mapped[str] = mapped_column(String(80))
    label_key: Mapped[str] = mapped_column(String(80))
    observation_id: Mapped[int | None] = mapped_column(
        ForeignKey("observations.id", ondelete="SET NULL"), nullable=True, index=True
    )

    entry_links: Mapped[list[ObservationBehavior]] = relationship(
        back_populates="tag", cascade="all, delete-orphan", lazy="selectin"
    )
    species: Mapped[Species] = relationship(back_populates="behavior_tags")
    observation: Mapped[Observation | None] = relationship()


class SpeciesIndividualTag(TimestampMixin, Base):
    __tablename__ = "species_individual_tags"
    __table_args__ = (
        UniqueConstraint("species_id", "label_key"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    species_id: Mapped[int] = mapped_column(
        ForeignKey("species.id", ondelete="CASCADE"), index=True
    )
    label: Mapped[str] = mapped_column(String(120))
    label_key: Mapped[str] = mapped_column(String(120))
    observation_id: Mapped[int | None] = mapped_column(
        ForeignKey("observations.id", ondelete="SET NULL"), nullable=True, index=True
    )

    species: Mapped[Species] = relationship(back_populates="individual_tags")
    observation: Mapped[Observation | None] = relationship()


class CollectionPlan(TimestampMixin, Base):
    __tablename__ = "collection_plans"
    __table_args__ = (
        CheckConstraint(
            "NOT (logo_asset_id IS NOT NULL AND logo_observation_species_id IS NOT NULL)",
            name="logo_single_source",
        ),
        CheckConstraint(
            "logo_crop_center_x >= 0 AND logo_crop_center_x <= 1",
            name="logo_crop_center_x_range",
        ),
        CheckConstraint(
            "logo_crop_center_y >= 0 AND logo_crop_center_y <= 1",
            name="logo_crop_center_y_range",
        ),
        CheckConstraint(
            "logo_crop_zoom >= 1 AND logo_crop_zoom <= 4",
            name="logo_crop_zoom_range",
        ),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(180))
    introduction: Mapped[str | None] = mapped_column(Text, nullable=True)
    template_kind: Mapped[str] = mapped_column(String(24))
    logo_asset_id: Mapped[int | None] = mapped_column(
        ForeignKey("media_assets.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    logo_observation_species_id: Mapped[int | None] = mapped_column(
        ForeignKey("observation_species.id", ondelete="SET NULL"), nullable=True, index=True
    )
    logo_crop_center_x: Mapped[float] = mapped_column(Float, default=0.5)
    logo_crop_center_y: Mapped[float] = mapped_column(Float, default=0.5)
    logo_crop_zoom: Mapped[float] = mapped_column(Float, default=1.0)

    logo_asset: Mapped[MediaAsset | None] = relationship(foreign_keys=[logo_asset_id])
    logo_observation_species: Mapped[ObservationSpecies | None] = relationship(
        foreign_keys=[logo_observation_species_id]
    )
    subitems: Mapped[list[CollectionPlanSubitem]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
        order_by="CollectionPlanSubitem.position",
    )
    memberships: Mapped[list[CollectionPlanSpecies]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
        order_by="CollectionPlanSpecies.position",
    )

    @property
    def catalog_number(self) -> str:
        return f"COL-{self.id:06d}"


class CollectionPlanSubitem(TimestampMixin, Base):
    __tablename__ = "collection_plan_subitems"
    __table_args__ = (
        UniqueConstraint("plan_id", "position"),
        UniqueConstraint("plan_id", "label_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("collection_plans.id", ondelete="CASCADE"), index=True
    )
    label: Mapped[str] = mapped_column(String(80))
    label_key: Mapped[str] = mapped_column(String(80))
    position: Mapped[int] = mapped_column(Integer)

    plan: Mapped[CollectionPlan] = relationship(back_populates="subitems")
    slots: Mapped[list[CollectionPlanSlot]] = relationship(
        back_populates="subitem", cascade="all, delete-orphan"
    )


class CollectionPlanSpecies(TimestampMixin, Base):
    __tablename__ = "collection_plan_species"
    __table_args__ = (
        UniqueConstraint("plan_id", "species_id"),
        UniqueConstraint("plan_id", "position"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("collection_plans.id", ondelete="CASCADE"), index=True
    )
    species_id: Mapped[int] = mapped_column(
        ForeignKey("species.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)
    introduction: Mapped[str | None] = mapped_column(Text, nullable=True)

    plan: Mapped[CollectionPlan] = relationship(back_populates="memberships")
    species: Mapped[Species] = relationship(back_populates="collection_memberships")
    slots: Mapped[list[CollectionPlanSlot]] = relationship(
        back_populates="membership", cascade="all, delete-orphan"
    )


class CollectionPlanSlot(TimestampMixin, Base):
    __tablename__ = "collection_plan_slots"
    __table_args__ = (
        UniqueConstraint("membership_id", "subitem_id"),
        CheckConstraint("crop_center_x >= 0 AND crop_center_x <= 1", name="crop_center_x_range"),
        CheckConstraint("crop_center_y >= 0 AND crop_center_y <= 1", name="crop_center_y_range"),
        CheckConstraint("crop_zoom >= 1 AND crop_zoom <= 4", name="crop_zoom_range"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    membership_id: Mapped[int] = mapped_column(
        ForeignKey("collection_plan_species.id", ondelete="CASCADE"), index=True
    )
    subitem_id: Mapped[int] = mapped_column(
        ForeignKey("collection_plan_subitems.id", ondelete="CASCADE"), index=True
    )
    observation_species_id: Mapped[int | None] = mapped_column(
        ForeignKey("observation_species.id", ondelete="SET NULL"), nullable=True, index=True
    )
    crop_center_x: Mapped[float] = mapped_column(Float, default=0.5)
    crop_center_y: Mapped[float] = mapped_column(Float, default=0.5)
    crop_zoom: Mapped[float] = mapped_column(Float, default=1.0)

    membership: Mapped[CollectionPlanSpecies] = relationship(back_populates="slots")
    subitem: Mapped[CollectionPlanSubitem] = relationship(back_populates="slots")
    observation_species: Mapped[ObservationSpecies | None] = relationship()


class ObservationBehavior(Base):
    """A behavior belongs to a species entry, never to every bird in a photograph."""

    __tablename__ = "observation_behaviors"

    tag_id: Mapped[int] = mapped_column(
        ForeignKey("species_behavior_tags.id", ondelete="CASCADE"), primary_key=True
    )
    observation_species_id: Mapped[int] = mapped_column(
        ForeignKey("observation_species.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    tag: Mapped[SpeciesBehaviorTag] = relationship(back_populates="entry_links", lazy="joined")
    entry: Mapped[ObservationSpecies] = relationship(back_populates="behavior_links")
