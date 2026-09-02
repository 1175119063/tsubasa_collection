import unicodedata
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .enums import (
    BodySize,
    ChinaProtectionStatus,
    EcologicalGroup,
    EvidenceDimension,
    HabitatType,
    IUCNStatus,
    LifeStage,
    LocationType,
    PhotoType,
    Season,
    Sex,
)


class TaxonNodeInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    chinese_name: str = Field(min_length=1, max_length=120)
    scientific_name: str = Field(min_length=1, max_length=120)


class SubspeciesInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    scientific_name: str = Field(min_length=1, max_length=220)
    chinese_name: str | None = Field(default=None, max_length=120)


class NewSpeciesInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    order: TaxonNodeInput
    family: TaxonNodeInput
    genus: TaxonNodeInput
    chinese_name: str = Field(min_length=1, max_length=120)
    scientific_name: str = Field(min_length=3, max_length=180)
    iucn_status: IUCNStatus
    china_protection_status: ChinaProtectionStatus | None
    has_subspecies: bool
    subspecies: list[SubspeciesInput] = Field(default_factory=list)
    notes: str | None = None

    @model_validator(mode="after")
    def validate_subspecies_list(self) -> "NewSpeciesInput":
        if self.has_subspecies and not self.subspecies:
            raise ValueError("有亚种的物种必须填写完整亚种名单")
        if not self.has_subspecies and self.subspecies:
            raise ValueError("无亚种物种不能提交亚种名单")
        normalized = {item.scientific_name.casefold() for item in self.subspecies}
        if len(normalized) != len(self.subspecies):
            raise ValueError("亚种名单中存在重复拉丁学名")
        return self


class ObservationSpeciesInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    species_id: int = Field(ge=1)
    subspecies_id: int | None = Field(default=None, ge=1)
    photo_type: PhotoType
    sex: Sex | None = None
    life_stage: LifeStage | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_subject(self) -> "ObservationSpeciesInput":
        if self.photo_type is PhotoType.INDIVIDUAL:
            if self.sex is None or self.life_stage is None:
                raise ValueError("个体照片必须填写性别和生命阶段")
        elif any(value is not None for value in (self.sex, self.life_stage, self.subspecies_id)):
            raise ValueError("群体照片不能填写性别、生命阶段或亚种")
        return self


class ObservationInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    species_id: int | None = Field(default=None, ge=1)
    location_id: int | None = Field(default=None, ge=1)
    new_species: NewSpeciesInput | None = None
    subspecies_id: int | None = Field(default=None, ge=1)
    subspecies_scientific_name: str | None = Field(default=None, max_length=220)
    photo_type: PhotoType
    observed_at: datetime
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    country_code: str = Field(min_length=2, max_length=8)
    country_name: str = Field(min_length=1, max_length=120)
    admin1_code: str = Field(min_length=1, max_length=40)
    admin1_name: str = Field(min_length=1, max_length=120)
    locality: str = Field(min_length=1, max_length=240)
    season: Season
    season_note: str | None = Field(default=None, max_length=120)
    sex: Sex | None = None
    life_stage: LifeStage | None = None
    notes: str | None = None
    additional_species: list[ObservationSpeciesInput] = Field(default_factory=list, max_length=9)

    @model_validator(mode="after")
    def validate_observation(self) -> "ObservationInput":
        if (self.species_id is None) == (self.new_species is None):
            raise ValueError("必须且只能选择已有物种或新增物种")
        if self.subspecies_id is not None and self.subspecies_scientific_name is not None:
            raise ValueError("亚种 ID 和亚种拉丁学名不能同时提交")
        if self.species_id is not None and self.subspecies_scientific_name is not None:
            raise ValueError("已有物种必须通过亚种 ID 选择亚种")
        if self.new_species is not None and self.subspecies_id is not None:
            raise ValueError("新增物种必须通过亚种拉丁学名选择亚种")
        if self.photo_type is PhotoType.INDIVIDUAL:
            if self.sex is None or self.life_stage is None:
                raise ValueError("个体照片必须填写性别和生命阶段")
        elif any(
            value is not None
            for value in (
                self.sex,
                self.life_stage,
                self.subspecies_id,
                self.subspecies_scientific_name,
            )
        ):
            raise ValueError("群体照片不能填写性别、生命阶段或亚种")
        if self.observed_at.tzinfo is not None:
            raise ValueError("拍摄时间应填写拍摄地点的当地时间，不包含时区")
        if self.observed_at.second or self.observed_at.microsecond:
            raise ValueError("拍摄时间必须精确到分钟")
        if self.season is not Season.OTHER and self.season_note:
            raise ValueError("只有季节为“其他”时才能填写季节说明")
        additional_ids = [item.species_id for item in self.additional_species]
        if len(additional_ids) != len(set(additional_ids)):
            raise ValueError("同一观察中不能重复添加同一物种")
        if self.species_id is not None and self.species_id in additional_ids:
            raise ValueError("主要物种不能在附加物种中重复出现")
        return self


class SpeciesAudioInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str | None = Field(default=None, max_length=160)
    notes: str | None = None
    recorded_at: datetime | None = None
    locality: str | None = Field(default=None, max_length=240)


class ObservationSelectionInput(BaseModel):
    observation_id: int | None = Field(default=None, ge=1)


class ObservationUpdateInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    sex: Sex | None = None
    life_stage: LifeStage | None = None
    subspecies_id: int | None = Field(default=None, ge=1)
    notes: str | None = None


class ArchiveEvidenceInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    dimension: EvidenceDimension
    value_key: str = Field(min_length=1, max_length=220)
    observation_id: int = Field(ge=1)


class BehaviorTagInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    label: str = Field(min_length=1, max_length=80)
    observation_id: int | None = Field(default=None, ge=1)


class IndividualTagInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    label: str = Field(min_length=1, max_length=120)
    observation_id: int | None = Field(default=None, ge=1)


class SpeciesProfileUpdateInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    introduction: str | None = Field(default=None, max_length=10000)
    order: TaxonNodeInput
    family: TaxonNodeInput
    genus: TaxonNodeInput
    ecological_group: EcologicalGroup = EcologicalGroup.UNKNOWN
    body_size: BodySize = BodySize.UNKNOWN
    preferred_habitats: list[HabitatType] = Field(default_factory=list, max_length=3)
    evidence_selections: list[ArchiveEvidenceInput] = Field(default_factory=list)
    behaviors: list[BehaviorTagInput] = Field(default_factory=list)
    individuals: list[IndividualTagInput] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_archives(self) -> "SpeciesProfileUpdateInput":
        if len(set(self.preferred_habitats)) != len(self.preferred_habitats):
            raise ValueError("偏好生境不能重复")
        supported = {
            EvidenceDimension.SEX,
            EvidenceDimension.LIFE_STAGE,
            EvidenceDimension.SUBSPECIES,
        }
        if any(item.dimension not in supported for item in self.evidence_selections):
            raise ValueError("只能为个体档案和亚种档案选择观察凭证")
        evidence_keys = {
            (item.dimension, item.value_key.casefold())
            for item in self.evidence_selections
        }
        if len(evidence_keys) != len(self.evidence_selections):
            raise ValueError("同一档案项不能重复选择观察凭证")
        behavior_keys = {
            " ".join(unicodedata.normalize("NFKC", item.label).split()).casefold()
            for item in self.behaviors
        }
        if len(behavior_keys) != len(self.behaviors):
            raise ValueError("行为标签不能重复")
        return self


class LocationInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str = Field(min_length=1, max_length=180)
    location_type: LocationType
    country_code: str = Field(min_length=2, max_length=8)
    country_name: str = Field(min_length=1, max_length=120)
    admin1_code: str = Field(min_length=1, max_length=40)
    admin1_name: str = Field(min_length=1, max_length=120)
    city: str | None = Field(default=None, max_length=120)
    district: str | None = Field(default=None, max_length=120)
    center_latitude: float = Field(ge=-90, le=90)
    center_longitude: float = Field(ge=-180, le=180)
    coordinate_system: Literal["wgs84", "gcj02"] = "wgs84"
    radius_meters: float | None = Field(default=None, gt=0)
    notes: str | None = None
    link_matching_records: bool = True


class LocationObservationSelectionInput(BaseModel):
    observation_ids: list[int] = Field(default_factory=list)


class TripInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=180)
    location_id: int | None = Field(default=None, ge=1)
    location_ids: list[int] = Field(default_factory=list, min_length=1)
    primary_location_id: int | None = Field(default=None, ge=1)
    started_at: datetime
    ended_at: datetime
    notes: str | None = None

    @model_validator(mode="after")
    def validate_trip_times(self) -> "TripInput":
        if not self.location_ids and self.location_id is not None:
            self.location_ids = [self.location_id]
        if not self.location_ids:
            raise ValueError("远征必须至少包含一个地点")
        if len(self.location_ids) != len(set(self.location_ids)):
            raise ValueError("远征地点不能重复")
        if self.primary_location_id is None:
            self.primary_location_id = self.location_id or self.location_ids[0]
        if self.primary_location_id not in self.location_ids:
            raise ValueError("主要地点必须属于远征地点")
        for value in (self.started_at, self.ended_at):
            if value.tzinfo is not None:
                raise ValueError("行程时间应使用当地时间，不包含时区")
            if value.second or value.microsecond:
                raise ValueError("行程时间必须精确到分钟")
        if self.ended_at <= self.started_at:
            raise ValueError("行程结束时间必须晚于开始时间")
        return self


class TripObservationSelectionInput(BaseModel):
    observation_ids: list[int] = Field(default_factory=list)


class CollectionPlanInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str = Field(min_length=1, max_length=180)
    introduction: str | None = Field(default=None, max_length=10000)
    template_kind: Literal["none", "plumage", "sex_age", "custom"]
    subitems: list[str] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def validate_collection_structure(self) -> "CollectionPlanInput":
        if self.template_kind == "custom":
            if not self.subitems:
                raise ValueError("自定义模板至少需要一个子项")
            keys = {
                " ".join(unicodedata.normalize("NFKC", label).split()).casefold()
                for label in self.subitems
            }
            if "" in keys or len(keys) != len(self.subitems):
                raise ValueError("自定义子项不能为空或重复")
            if any(len(label) > 80 for label in self.subitems):
                raise ValueError("自定义子项不能超过 80 个字符")
        elif self.subitems:
            raise ValueError("预设模板不接受自定义子项")
        return self


class CollectionPlanSpeciesInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    species_ids: list[int] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_species_ids(self) -> "CollectionPlanSpeciesInput":
        if len(self.species_ids) != len(set(self.species_ids)):
            raise ValueError("同一收集计划中不能重复添加同一物种")
        if any(species_id < 1 for species_id in self.species_ids):
            raise ValueError("物种 ID 必须大于零")
        return self


class CollectionSpeciesIntroductionInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    introduction: str | None = Field(default=None, max_length=10000)


class CollectionSlotEvidenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observation_species_id: int | None = Field(default=None, ge=1)
    crop_center_x: float = Field(default=0.5, ge=0, le=1)
    crop_center_y: float = Field(default=0.5, ge=0, le=1)
    crop_zoom: float = Field(default=1, ge=1, le=4)


class CollectionLogoInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observation_species_id: int | None = Field(default=None, ge=1)
    crop_center_x: float = Field(default=0.5, ge=0, le=1)
    crop_center_y: float = Field(default=0.5, ge=0, le=1)
    crop_zoom: float = Field(default=1, ge=1, le=4)
