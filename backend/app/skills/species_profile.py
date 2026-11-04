"""Read-only species-profile completion from online sources and current notes."""

from __future__ import annotations

from ..assistant_schemas import AssistantSpeciesProfileDraft, SpeciesProfileChunkReview
from ..feather_assistant import FeatherAssistant, FeatherAssistantError
from .base import SkillError
from .online_species import OnlineSpeciesSkill

_MAX_WIKI_EXCERPT = 4000
_CHUNK_CHARS = 3000
_MAX_CHUNKS = 8
_MAX_FINAL_INTRO = 3000
_MAX_NOTES = 16


def _profile_chunks(existing: str, excerpt: str) -> list[dict[str, str]]:
    """Split both inputs into fixed-size reading passes."""
    chunks: list[dict[str, str]] = []
    for source, text in (
        ("existing_introduction", existing),
        ("wikipedia", excerpt),
    ):
        if not text:
            continue
        for offset in range(0, len(text), _CHUNK_CHARS):
            piece = text[offset : offset + _CHUNK_CHARS].strip()
            if piece:
                chunks.append({"source": source, "text": piece})
    return chunks[:_MAX_CHUNKS]


def _append_notes(notes: list[str], incoming: list[str]) -> None:
    for item in incoming:
        text = str(item).strip()[:240]
        if text and text not in notes:
            notes.append(text)
        if len(notes) >= _MAX_NOTES:
            break


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

    def _review_chunk(
        self,
        species: dict,
        notes: list[str],
        missing: str | None,
        index: int,
        total: int,
        chunk: dict[str, str],
    ) -> SpeciesProfileChunkReview:
        assert self.assistant is not None
        try:
            return self.assistant.review_species_profile_chunk(
                {
                    "species": species,
                    "chunk": {
                        "index": index,
                        "total": total,
                        "source": chunk["source"],
                        "text": chunk["text"],
                    },
                    "notes_so_far": notes,
                    "missing_so_far": missing,
                }
            )
        except FeatherAssistantError as exc:
            raise SkillError(
                f"AI 整理暂时不可用：{exc.message}；简介没有修改。", 503
            ) from exc
        except Exception as exc:  # optional AI must not cause a partial overwrite
            raise SkillError(f"AI 整理暂时不可用：{exc}；简介没有修改。", 503) from exc

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

        species = {
            "chinese_name": chinese_name,
            "scientific_name": scientific_name,
            "inat_name": taxon.get("name"),
            "inat_common_name": taxon.get("common_name"),
            "classification": taxon.get("classification"),
        }
        wiki_evidence = (
            {
                "title": wiki.get("title"),
                "url": wiki.get("url"),
                "excerpt": excerpt,
            }
            if wiki.get("available") and excerpt
            else None
        )

        if len(existing) + len(excerpt) <= _CHUNK_CHARS:
            evidence = {
                "species": species,
                "existing_introduction": existing,
                "online_summary": taxon.get("summary"),
                "wikipedia": wiki_evidence,
            }
        else:
            chunks = _profile_chunks(existing, excerpt)
            notes: list[str] = []
            missing: str | None = None
            stopped = "exhausted"
            read = 0
            for index, chunk in enumerate(chunks, start=1):
                review = self._review_chunk(
                    species, notes, missing, index, len(chunks), chunk
                )
                _append_notes(notes, review.notes)
                missing = review.missing or None
                read = index
                if review.enough:
                    stopped = "enough"
                    break

            final_intro = existing if len(existing) <= _MAX_FINAL_INTRO else ""
            if len(existing) > _MAX_FINAL_INTRO:
                warnings.append(
                    "原简介较长，AI 已分段阅读；请核对生成稿是否保留了你需要的内容。"
                )
            if stopped == "enough" and read < len(chunks):
                warnings.append(
                    f"AI 判断资料已足够，剩余 {len(chunks) - read} 段未读取。"
                )
            if missing and stopped != "enough":
                warnings.append(f"资料中未找到：{missing}")
            if not notes and not final_intro and not taxon.get("summary"):
                raise SkillError("没有整理出可用的物种资料，简介没有修改。", 502)
            evidence = {
                "species": species,
                "existing_introduction": final_intro,
                "research_notes": notes,
                "online_summary": taxon.get("summary"),
                "wikipedia": None,
                "research": {
                    "chunks_read": read,
                    "chunks_total": len(chunks),
                    "stopped": stopped,
                    "input_chars": len(existing) + len(excerpt),
                },
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
