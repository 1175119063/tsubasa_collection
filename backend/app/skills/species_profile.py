"""Read-only species-profile completion from online sources and current notes."""

from __future__ import annotations

from ..assistant_schemas import AssistantSpeciesProfileDraft
from ..feather_assistant import FeatherAssistant, FeatherAssistantError
from .base import SkillError
from .online_species import OnlineSpeciesSkill

_MAX_WIKI_EXCERPT = 4000


class SpeciesProfileSkill:
    """Draft a profile introduction; the caller decides whether to save it."""

    name = "species_profile"

    def __init__(
        self,
        assistant: FeatherAssistant | None = None,
        *,
        online: OnlineSpeciesSkill | None = None,
    ) -> None:
        self.assistant = assistant
        self.online = online or OnlineSpeciesSkill()

    def draft(
        self,
        scientific_name: str,
        chinese_name: str | None,
        introduction: str,
    ) -> dict:
        if not self.assistant:
            raise SkillError("飞羽精灵未启用，简介没有修改。", 503)
        lookup = self.online.collect(scientific_name, fallback_query=chinese_name)
        taxon = lookup["taxon"]
        wiki = lookup.get("wikipedia") or {}
        warnings = list(lookup.get("warnings") or [])
        existing = introduction.strip()
        excerpt = str(wiki.get("excerpt") or "")[:_MAX_WIKI_EXCERPT]
        if not existing and not taxon.get("summary") and not excerpt:
            raise SkillError("没有可用的物种资料，简介保持不变。", 502)

        evidence = {
            "species": {
                "chinese_name": chinese_name,
                "scientific_name": scientific_name,
                "inat_name": taxon.get("name"),
                "inat_common_name": taxon.get("common_name"),
                "classification": taxon.get("classification"),
            },
            "existing_introduction": existing,
            "online_summary": taxon.get("summary"),
            "wikipedia": (
                {
                    "title": wiki.get("title"),
                    "url": wiki.get("url"),
                    "excerpt": excerpt,
                }
                if wiki.get("available") and excerpt
                else None
            ),
        }
        try:
            draft: AssistantSpeciesProfileDraft = self.assistant.draft_species_profile(
                evidence
            )
        except FeatherAssistantError as exc:
            raise SkillError(f"AI 整理暂时不可用：{exc.message}；简介没有修改。", 503) from exc
        except Exception as exc:  # optional AI must not turn into a partial overwrite
            raise SkillError(f"AI 整理暂时不可用：{exc}；简介没有修改。", 503) from exc

        text = draft.introduction.strip()
        if not text:
            raise SkillError("AI 没有生成有效内容，简介没有修改。", 502)
        warnings.extend(draft.warnings)
        if taxon.get("name") and taxon["name"].casefold() != scientific_name.casefold():
            warnings.append(
                f"iNaturalist 将该名称解析为 {taxon['name']}，请核对物种后再保存。"
            )
        sources: list[dict] = []
        if taxon.get("url"):
            sources.append({"title": "iNaturalist", "url": taxon["url"]})
        if wiki.get("available") and wiki.get("url"):
            sources.append({"title": "Wikipedia", "url": wiki["url"]})
        return {
            "introduction": text,
            "warnings": list(dict.fromkeys(item for item in warnings if item)),
            "sources": sources,
        }
