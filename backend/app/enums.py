from enum import StrEnum


class IUCNStatus(StrEnum):
    NE = "NE"
    LC = "LC"
    NT = "NT"
    VU = "VU"
    EN = "EN"
    CR = "CR"
    EW = "EW"
    EX = "EX"


class ChinaProtectionStatus(StrEnum):
    THREE_PROTECTED = "three_protected"
    LEVEL_2 = "level_2"
    LEVEL_1 = "level_1"


class PhotoType(StrEnum):
    INDIVIDUAL = "individual"
    GROUP = "group"


class Sex(StrEnum):
    MALE = "male"
    FEMALE = "female"
    UNKNOWN = "unknown"


class LifeStage(StrEnum):
    EGG = "egg"
    CHICK = "chick"
    SUBADULT = "subadult"
    ADULT = "adult"
    UNKNOWN = "unknown"


class Season(StrEnum):
    SPRING = "spring"
    SUMMER = "summer"
    AUTUMN = "autumn"
    WINTER = "winter"
    OTHER = "other"


class MediaKind(StrEnum):
    PHOTO = "photo"
    AUDIO = "audio"


class LocationType(StrEnum):
    WETLAND_PARK = "wetland_park"
    FOREST_PARK = "forest_park"
    URBAN_PARK = "urban_park"
    NATURE_RESERVE = "nature_reserve"
    RESERVOIR = "reservoir"
    FARMLAND = "farmland"
    COAST = "coast"
    OTHER = "other"


class EvidenceDimension(StrEnum):
    COUNTRY = "country"
    ADMIN1 = "admin1"
    SEASON = "season"
    SEX = "sex"
    LIFE_STAGE = "life_stage"
    SUBSPECIES = "subspecies"


class EcologicalGroup(StrEnum):
    UNKNOWN = "unknown"
    RAPTOR = "raptor"
    SONGBIRD = "songbird"
    LANDFOWL = "landfowl"
    SCANSORIAL = "scansorial"
    WADER = "wader"
    WATERFOWL = "waterfowl"


class BodySize(StrEnum):
    UNKNOWN = "unknown"
    SMALL = "small"
    SMALL_MEDIUM = "small_medium"
    MEDIUM = "medium"
    MEDIUM_LARGE = "medium_large"
    LARGE = "large"


class HabitatType(StrEnum):
    CITY = "city"
    FARMLAND = "farmland"
    GRASSLAND = "grassland"
    SHRUB = "shrub"
    FOREST = "forest"
    WETLAND = "wetland"
    RIVER = "river"
    LAKE = "lake"
    DESERT = "desert"
    COAST = "coast"
    OCEAN = "ocean"
    MUDFLAT = "mudflat"
    ALPINE = "alpine"
    OTHER = "other"
