"""Small, explicit contracts shared by the read-only skills."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


class SkillError(RuntimeError):
    """A skill could not complete for a reason the HTTP boundary understands."""

    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class SkillContext:
    """Non-authoritative context supplied by the form, never written back."""

    latitude: float | None = None
    longitude: float | None = None
    locality: str | None = None
    country: str | None = None
    admin1: str | None = None
    observed_at: datetime | None = None

    @property
    def has_coordinates(self) -> bool:
        return self.latitude is not None and self.longitude is not None


class Skill(Protocol):
    name: str

    def run(self, query: str, context: SkillContext | None = None) -> dict: ...
