from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from .models import Observation, Species


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
