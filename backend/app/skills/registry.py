"""Tiny registry so future skills plug into the same read-only contract."""

from __future__ import annotations

from ..feather_assistant import FeatherAssistant
from .base import Skill
from .online_species import OnlineSpeciesSkill
from .species_profile import SpeciesProfileSkill

SKILLS: dict[str, type[Skill]] = {
    "online_species": OnlineSpeciesSkill,
    "species_profile": SpeciesProfileSkill,
}


def build_skill(name: str, assistant: FeatherAssistant | None = None) -> Skill:
    try:
        skill_type = SKILLS[name]
    except KeyError as exc:
        raise KeyError(f"unknown skill: {name}") from exc
    return skill_type(assistant=assistant)
