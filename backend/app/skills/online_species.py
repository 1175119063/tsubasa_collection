"""Read-only online species lookup and evidence-backed subspecies advice."""

from __future__ import annotations

import re

from ..assistant_schemas import AssistantOnlineSpeciesAdvice
from ..feather_assistant import FeatherAssistant, FeatherAssistantError
from ..inat_mcp import inat_api
from ..wikipedia_api import fetch_extract
from .base import SkillContext, SkillError

_CJK = re.compile(r"[\u3400-\u9fff]")
_SOURCES = ["iNaturalist", "Wikipedia"]


def valid_taxon(taxon: dict | None) -> bool:
    return bool(
        taxon
        and taxon.get("is_bird") is True
        and taxon.get("is_active") is True
        and taxon.get("rank") == "species"
        and taxon.get("name")
    )


def enrich_taxon(taxon: dict) -> dict:
    """Add the small form draft without inventing Chinese names."""

    def node(item: dict | None) -> dict:
        item = item or {}
        common = item.get("common_name") or ""
        return {
            "chinese_name": common if _CJK.search(common) else None,
            "scientific_name": item.get("name"),
        }

    classification = taxon.get("classification") or {}
    return {
        **taxon,
        "draft": {
            **{rank: node(classification.get(rank)) for rank in ("order", "family", "genus")},
            "species": node(taxon),
        },
    }


class OnlineSpeciesSkill:
    name = "online_species"

    def __init__(
        self,
        assistant: FeatherAssistant | None = None,
        *,
        wiki_fetcher=fetch_extract,
    ) -> None:
        self.assistant = assistant
        self._wiki_fetcher = wiki_fetcher

    # ------------------------------------------------------------------ search
    def search(self, query: str, context: SkillContext | None = None) -> dict:
        try:
            resolved = inat_api.resolve_name(query, use_aliases=False)
        except inat_api.InatError as exc:
            raise _inat_failure(exc) from exc

        warnings = list(resolved.get("warnings") or [])
        taxon = resolved.get("taxon")
        if taxon and not valid_taxon(taxon):
            warnings.append("来源匹配到的条目不是有效的鸟类物种，请改用完整学名查询。")
            taxon = None
        if not taxon:
            return {
                "query": query,
                "resolved": False,
                "via": None,
                "wikidata": resolved.get("wikidata"),
                "taxon": None,
                "candidates": [
                    item
                    for item in resolved.get("candidates", [])
                    if valid_taxon(item)
                ],
                "warnings": warnings,
                "ai": _ai_unavailable("尚未确认物种，未进行亚种建议。"),
            }

        taxon = enrich_taxon(taxon)
        children = list(taxon.get("children") or [])
        if not children and taxon.get("children_count"):
            try:
                children = inat_api.get_taxon_children(taxon["id"]).get("results", [])
            except inat_api.InatError as exc:
                warnings.append(f"亚种列表获取失败：{_message(exc)}")
        taxon["children"] = children

        nearby: dict | None = None
        if children and context and context.has_coordinates:
            try:
                nearby = inat_api.nearby_subspecies(
                    taxon["id"],
                    context.latitude,
                    context.longitude,
                    radius_km=50,
                )
            except inat_api.InatError as exc:
                warnings.append(f"附近亚种记录获取失败：{_message(exc)}")
        elif children and context and context.latitude is not None:
            warnings.append("经纬度不完整，未统计附近的亚种记录。")

        wiki_full = self._wikipedia(taxon, warnings)
        wiki_public = {
            key: value for key, value in wiki_full.items() if key not in {"extract", "tried"}
        }
        if wiki_full.get("available") and not wiki_full.get("excerpt"):
            warnings.append("维基百科条目里没有找到分布或亚种段落。")

        ai = self._advise(taxon, children, nearby, wiki_full, context)
        if children and not nearby and context and context.has_coordinates:
            if ai.get("available"):
                ai.setdefault("warnings", []).append(
                    "附近没有可用的亚种级记录，AI 只能依据分布文字给出低置信度建议。"
                )

        return {
            "query": query,
            "resolved": True,
            "via": resolved.get("via"),
            "wikidata": resolved.get("wikidata"),
            "taxon": taxon,
            "candidates": [],
            "warnings": warnings,
            "nearby": nearby,
            "wikipedia": wiki_public,
            "ai": ai,
        }

    # ------------------------------------------------------------------ collect
    def collect(self, query: str, fallback_query: str | None = None) -> dict:
        """Fetch the taxon and Wikipedia material without subspecies advice."""

        candidates = [item for item in (query, fallback_query) if item]
        warnings: list[str] = []
        resolved: dict | None = None
        via: str | None = None
        wikidata: dict | None = None
        used: str | None = None
        for index, candidate in enumerate(candidates):
            try:
                resolved = inat_api.resolve_name(candidate, use_aliases=False)
            except inat_api.InatError as exc:
                raise _inat_failure(exc) from exc
            via = resolved.get("via")
            wikidata = resolved.get("wikidata")
            warnings.extend(resolved.get("warnings") or [])
            if resolved.get("resolved") and valid_taxon(resolved.get("taxon")):
                used = candidate
                if index:
                    warnings.append(f"按学名未找到，已改用“{candidate}”查询。")
                break
            resolved = None
        if not resolved or not resolved.get("taxon"):
            raise SkillError("未找到该物种，请检查中文名或学名。", 404)
        taxon = enrich_taxon(resolved["taxon"])
        wiki = self._wikipedia(taxon, warnings)
        return {
            "query": used or query,
            "resolved": True,
            "via": via,
            "wikidata": wikidata,
            "taxon": taxon,
            "wikipedia": wiki,
            "warnings": warnings,
        }

    # ------------------------------------------------------------------ detail
    def detail(self, taxon_id: int) -> dict:
        try:
            taxon = inat_api.get_taxon(taxon_id)
        except inat_api.InatError as exc:
            raise _inat_failure(exc) from exc
        if taxon.get("id") != taxon_id or not valid_taxon(taxon):
            raise SkillError("该条目不是有效的鸟类物种，无法用于物种录入。", 422)
        return enrich_taxon(taxon)

    # --------------------------------------------------------------- wikipedia
    def _wikipedia(self, taxon: dict, warnings: list[str]) -> dict:
        common = taxon.get("common_name") or ""
        english = taxon.get("english_common_name") or taxon.get("name") or ""
        title = common if _CJK.search(common) else (taxon.get("name") or "")
        fallbacks = tuple(item for item in (english, taxon.get("name")) if item)
        try:
            return self._wiki_fetcher(
                url=taxon.get("wikipedia_url"),
                title=title,
                lang="zh",
                fallback_titles=fallbacks,
                use_cache=True,
            )
        except Exception as exc:  # Wikipedia is optional; keep iNat usable.
            warnings.append(f"维基百科资料获取失败：{exc}")
            return {
                "available": False,
                "message": "维基百科暂时不可用，已保留 iNaturalist 资料。",
            }

    # --------------------------------------------------------------- AI advice
    def _advise(
        self,
        taxon: dict,
        children: list[dict],
        nearby: dict | None,
        wiki: dict,
        context: SkillContext | None,
    ) -> dict:
        if not self.assistant:
            return _ai_unavailable("飞羽精灵未启用；以下仅为 iNaturalist/维基资料。")
        if not children:
            return _ai_unavailable("iNaturalist 未列出该物种的亚种，无需 AI 排序。")
        if not context or not context.has_coordinates:
            return _ai_unavailable(
                "未提供拍摄地点经纬度，未做亚种推断；可从 iNaturalist 列表手动选择。"
            )
        evidence = {
            "species": {
                "id": taxon.get("id"),
                "name": taxon.get("name"),
                "common_name": taxon.get("common_name"),
                "english_common_name": taxon.get("english_common_name"),
                "rank": taxon.get("rank"),
            },
            "subspecies_candidates": [
                {
                    "taxon_id": item.get("id"),
                    "name": item.get("name"),
                    "common_name": item.get("common_name"),
                    "observations_count": item.get("observations_count"),
                }
                for item in children[:30]
            ],
            "location": {
                "latitude": round(float(context.latitude), 2),
                "longitude": round(float(context.longitude), 2),
                "locality": context.locality,
                "country": context.country,
                "admin1": context.admin1,
                "observed_at": (
                    context.observed_at.isoformat()
                    if context.observed_at is not None
                    else None
                ),
            },
            "nearby_subspecies": (
                {
                    "radius_km": nearby.get("radius_km"),
                    "total_results": nearby.get("total_results"),
                    "returned": nearby.get("returned"),
                    "truncated": nearby.get("truncated"),
                    "counts": (nearby.get("counts") or [])[:12],
                }
                if nearby
                else None
            ),
            "conservation": (taxon.get("conservation") or [])[:20],
            "wikipedia": (
                {"title": wiki.get("title"), "excerpt": wiki.get("excerpt")}
                if wiki.get("available")
                else None
            ),
        }
        try:
            advice: AssistantOnlineSpeciesAdvice = self.assistant.advise_online_species(
                evidence
            )
        except FeatherAssistantError as exc:
            return _ai_unavailable(f"AI 整理暂时不可用：{exc.message}")
        except Exception as exc:  # never turn an optional explanation into an outage
            return _ai_unavailable(f"AI 整理暂时不可用：{exc}")

        known = {item.get("id"): item for item in children}
        suggestions: list[dict] = []
        dropped = 0
        for item in advice.subspecies:
            child = known.get(item.taxon_id)
            if child is None:
                dropped += 1
                continue
            suggestions.append(
                {
                    **child,
                    "confidence": item.confidence,
                    "reason": item.reason,
                }
            )
        warnings = list(advice.warnings)
        if dropped:
            warnings.append("AI 返回了不在候选中的亚种编号，已丢弃。")
        if not suggestions:
            warnings.append("资料不足以给出亚种建议，请自行核对 iNaturalist 列表。")
        return {
            "available": True,
            "message": (
                "AI 仅按给定资料排序候选，不会自动选中或写入数据库。"
                if suggestions
                else "AI 没有给出可靠候选，请自行核对资料。"
            ),
            "subspecies": suggestions,
            "warnings": warnings,
            "sources": _SOURCES,
        }


def _ai_unavailable(message: str) -> dict:
    return {
        "available": False,
        "message": message,
        "subspecies": [],
        "warnings": [],
        "sources": _SOURCES,
    }


def _message(exc: Exception) -> str:
    return str(exc).strip() or "未知错误"


def _inat_failure(exc: inat_api.InatError) -> SkillError:
    status = exc.status or 0
    text = _message(exc)
    if status == 404:
        return SkillError("未找到该物种，请检查名称或编号。", 404)
    if status == 429:
        return SkillError("资料来源请求过于频繁，请稍后重试。", 429)
    if status in {401, 403}:
        return SkillError("资料来源暂时拒绝访问，请稍后重试。", 503)
    if "超时" in text:
        return SkillError("在线查询超时，请稍后重试或改用学名。", 504)
    if "network error" in text.lower():
        return SkillError("无法连接资料来源，请检查网络后重试。", 503)
    return SkillError("暂时无法获取在线资料，请稍后重试。", 502)
