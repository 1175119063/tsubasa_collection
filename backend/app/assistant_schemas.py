from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AssistantTextInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    text: str = Field(min_length=2, max_length=6000)


class AssistantTaxon(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    chinese_name: str | None = Field(default=None, max_length=120)
    scientific_name: str | None = Field(default=None, max_length=220)
    evidence: str | None = Field(default=None, max_length=300)

    @field_validator("chinese_name", "scientific_name", "evidence", mode="before")
    @classmethod
    def empty_string_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value


class AssistantSpeciesExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order: AssistantTaxon
    family: AssistantTaxon
    genus: AssistantTaxon
    species: AssistantTaxon
    subspecies: list[AssistantTaxon] = Field(default_factory=list, max_length=50)
    missing_fields: list[str] = Field(default_factory=list, max_length=20)
    warnings: list[str] = Field(default_factory=list, max_length=20)


class AssistantTaxonomyResearchInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    query: str = Field(min_length=2, max_length=300)


class OnlineSpeciesSearchInput(BaseModel):
    """Lookup input; coordinates are optional and never persisted here."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    query: str = Field(min_length=2, max_length=300)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    locality: str | None = Field(default=None, max_length=240)
    observed_at: datetime | None = None

    @model_validator(mode="after")
    def coordinates_must_be_a_pair(self) -> "OnlineSpeciesSearchInput":
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("经纬度必须同时提供")
        return self


class OnlineSubspeciesSuggestion(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    taxon_id: int = Field(gt=0)
    reason: str = Field(min_length=1, max_length=400)
    confidence: Literal["high", "medium", "low"] = "low"


class AssistantOnlineSpeciesAdvice(BaseModel):
    """Model output is advice only; the skill filters ids against iNat children."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    subspecies: list[OnlineSubspeciesSuggestion] = Field(default_factory=list, max_length=12)
    warnings: list[str] = Field(default_factory=list, max_length=10)


class SpeciesProfileInput(BaseModel):
    """The form sends its current, possibly unsaved introduction for integration."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    scientific_name: str = Field(min_length=2, max_length=180)
    chinese_name: str | None = Field(default=None, max_length=120)
    introduction: str = Field(default="", max_length=10000)


class AssistantSpeciesProfileDraft(BaseModel):
    """Model output is a draft only; the API never writes it to the database."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    introduction: str = Field(min_length=1, max_length=10000)
    warnings: list[str] = Field(default_factory=list, max_length=10)


class SpeciesProfileChunkReview(BaseModel):
    """One fixed-size reading pass; the skill decides whether to read further."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    notes: list[str] = Field(default_factory=list, max_length=4)
    enough: bool = False
    missing: str | None = Field(default=None, max_length=200)


class AssistantKnowledgeSearchPlan(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    query_terms: list[str] = Field(min_length=1, max_length=8)


class AssistantKnowledgeCitation(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    source_id: str = Field(min_length=1, max_length=260)
    title: str = Field(min_length=1, max_length=500)
    locator: str = Field(min_length=1, max_length=100)
    excerpt: str = Field(min_length=1, max_length=1800)


class AssistantTaxonomyResearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    extraction: AssistantSpeciesExtraction
    citations: list[AssistantKnowledgeCitation] = Field(default_factory=list, max_length=8)


class AssistantSearchInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    query: str = Field(min_length=2, max_length=500)


SearchParameter = str | int | float | bool | None


class AssistantSqlQuery(BaseModel):
    """A model-produced, parameterized query against the field-journal views."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    interpretation: str = Field(min_length=1, max_length=500)
    sql: str = Field(min_length=10, max_length=8000)
    parameters: dict[str, SearchParameter] = Field(default_factory=dict, max_length=50)
    sort: Literal["asc", "desc"] = "desc"
    warnings: list[str] = Field(default_factory=list, max_length=10)


class AssistantSearchExtraction(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    year: int | None = Field(default=None, ge=1900, le=2100)
    month: int | None = Field(default=None, ge=1, le=12)
    species_name: str | None = Field(default=None, max_length=180)
    location_name: str | None = Field(default=None, max_length=240)
    trip_name: str | None = Field(default=None, max_length=240)
    sort: Literal["asc", "desc"] | None = None
    multi_species_only: bool | None = None
    warnings: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("species_name", "location_name", "trip_name", mode="before")
    @classmethod
    def empty_search_string_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value


class AssistantHelpInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    page: Literal["home", "observations", "dex", "locations", "trips"]
    question: str = Field(min_length=2, max_length=500)


class AssistantHelpResponse(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    answer: str = Field(min_length=1, max_length=3000)
    suggestions: list[str] = Field(default_factory=list, max_length=4)


class AssistantChatMessage(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=3000)


class AssistantChatInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    page: Literal["home", "observations", "dex", "locations", "trips"]
    messages: list[AssistantChatMessage] = Field(min_length=1, max_length=12)

    @model_validator(mode="after")
    def last_message_must_be_user(self) -> "AssistantChatInput":
        if self.messages[-1].role != "user":
            raise ValueError("最后一条消息必须来自用户")
        return self


class AmapIntegrationInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    api_key: str | None = Field(default=None, min_length=4, max_length=200)
    clear_api_key: bool = False


class TiandituIntegrationInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    api_key: str | None = Field(default=None, min_length=4, max_length=200)
    clear_api_key: bool = False


class LlmIntegrationInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    provider: Literal["local", "openai_compatible"]
    base_url: str | None = Field(default=None, max_length=500)
    model: str | None = Field(default=None, max_length=200)
    api_key: str | None = Field(default=None, min_length=4, max_length=1000)
    clear_api_key: bool = False

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str | None) -> str | None:
        if not value:
            return None
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("Base URL 必须是完整的 HTTP(S) 地址")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Base URL 不能包含账号、密码、查询参数或片段")
        local_hosts = {"127.0.0.1", "localhost", "::1"}
        if parsed.scheme != "https" and parsed.hostname not in local_hosts:
            raise ValueError("远程大模型的 Base URL 必须使用 HTTPS")
        return value.rstrip("/")
