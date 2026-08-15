from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .enums import (
    ChinaProtectionStatus,
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
    radius_meters: float | None = Field(default=None, gt=0)
    notes: str | None = None
    link_matching_records: bool = True


class LocationObservationSelectionInput(BaseModel):
    observation_ids: list[int] = Field(default_factory=list)


class TripInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    location_id: int = Field(ge=1)
    started_at: datetime
    ended_at: datetime
    notes: str | None = None

    @model_validator(mode="after")
    def validate_trip_times(self) -> "TripInput":
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
