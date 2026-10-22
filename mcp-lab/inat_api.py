"""Read-only iNaturalist lookup used by the MCP lab.

Standard library only: the real application deliberately has no HTTP client
dependency, and this experiment should not add one either.

Every payload carries provenance (source URL, fetch time, cache flag) because
the point of the experiment is to see what an *evidence-backed* auto-fill
would look like, not to build a scraper.
"""

from __future__ import annotations

import hashlib
import html
import json
import pathlib
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

BASE_URL = "https://api.inaturalist.org/v1"
WIKIDATA_URL = "https://www.wikidata.org/w/api.php"
USER_AGENT = "Tsubasa-MCP-Lab/0.1 (local experiment; read-only)"
LAB_DIR = pathlib.Path(__file__).resolve().parent
CACHE_DIR = LAB_DIR / "cache"
ALIASES_LOCAL = LAB_DIR / "aliases.local.json"
ALIASES_EXAMPLE = LAB_DIR / "aliases.example.json"
DEFAULT_TTL = 30 * 24 * 60 * 60.0
CJK = re.compile(r"[\u3400-\u9fff]")
HTML_TAG = re.compile(r"<[^>]+>")


class InatError(RuntimeError):
    """A lookup failed (network, upstream status, or unusable payload)."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _get_json(url: str, timeout: float = 20.0) -> dict:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read()[:300].decode("utf-8", "replace")
        raise InatError(f"upstream HTTP {exc.code}: {detail}", exc.code) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise InatError(f"upstream network error: {exc}") from exc
    try:
        data = json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise InatError("upstream returned invalid JSON") from exc
    if not isinstance(data, dict):
        raise InatError("upstream returned an unexpected payload")
    return data


def _cache_key(kind: str, params: dict) -> str:
    raw = json.dumps(params, sort_keys=True, ensure_ascii=False)
    return f"{kind}-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]}"


def _read_cache(kind: str, params: dict, ttl: float) -> dict | None:
    path = CACHE_DIR / f"{_cache_key(kind, params)}.json"
    if not path.is_file():
        return None
    if time.time() - path.stat().st_mtime > ttl:
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _write_cache(kind: str, params: dict, payload: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{_cache_key(kind, params)}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _taxon_url(taxon_id: object) -> str | None:
    return f"https://www.inaturalist.org/taxa/{taxon_id}" if taxon_id else None


def _strip_html(value: str | None) -> str | None:
    if not value:
        return None
    text = HTML_TAG.sub("", value)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _compact_list_item(item: dict) -> dict:
    return {
        "id": item.get("id"),
        "name": item.get("name"),
        "common_name": item.get("preferred_common_name"),
        "english_common_name": item.get("english_common_name"),
        "rank": item.get("rank"),
        "is_active": item.get("is_active"),
        "observations_count": item.get("observations_count"),
        "matched_term": item.get("matched_term"),
        "url": _taxon_url(item.get("id")),
    }


def _compact_ancestor(item: dict) -> dict:
    return {
        "id": item.get("id"),
        "rank": item.get("rank"),
        "name": item.get("name"),
        "common_name": item.get("preferred_common_name"),
    }


def normalize_taxon(item: dict, *, fetched_at: str, cached: bool) -> dict:
    ancestors = [_compact_ancestor(entry) for entry in (item.get("ancestors") or [])]
    by_rank = {entry["rank"]: entry for entry in ancestors if entry.get("rank")}
    classification = {
        rank: (
            {"name": by_rank[rank].get("name"), "common_name": by_rank[rank].get("common_name")}
            if rank in by_rank
            else None
        )
        for rank in ("order", "family", "genus")
    }
    conservation = []
    for entry in item.get("conservation_statuses") or []:
        if entry.get("status"):
            conservation.append(
                {
                    "status": entry.get("status"),
                    "authority": entry.get("authority"),
                    "place": (entry.get("place") or {}).get("name"),
                }
            )
    photo = item.get("default_photo") or {}
    taxon_id = item.get("id")
    return {
        "id": taxon_id,
        "name": item.get("name"),
        "common_name": item.get("preferred_common_name"),
        "english_common_name": item.get("english_common_name"),
        "rank": item.get("rank"),
        "is_active": item.get("is_active"),
        "extinct": item.get("extinct"),
        "ancestors": ancestors,
        "classification": classification,
        "summary": _strip_html(item.get("wikipedia_summary")),
        "wikipedia_url": item.get("wikipedia_url"),
        "conservation": conservation,
        "photo": {
            "attribution": photo.get("attribution"),
            "license": photo.get("license_code"),
            "url": photo.get("medium_url") or photo.get("url"),
        }
        if photo
        else None,
        "observations_count": item.get("observations_count"),
        "url": _taxon_url(taxon_id),
        "source_url": f"{BASE_URL}/taxa/{taxon_id}",
        "fetched_at": fetched_at,
        "cached": cached,
    }


def search_taxa(
    query: str,
    locale: str = "zh-CN",
    limit: int = 5,
    rank: str | None = None,
    *,
    use_cache: bool = True,
    ttl: float = DEFAULT_TTL,
) -> dict:
    text = (query or "").strip()
    if not text:
        raise InatError("query must not be empty")
    limit = max(1, min(int(limit or 5), 20))
    params = {"q": text, "locale": locale, "per_page": limit}
    if rank:
        params["rank"] = rank
    cache_key = {"kind": "search", **params}
    if use_cache:
        cached = _read_cache("search", cache_key, ttl)
        if cached is not None:
            cached["cached"] = True
            return cached
    url = f"{BASE_URL}/taxa?{urllib.parse.urlencode(params)}"
    data = _get_json(url)
    results = [_compact_list_item(item) for item in (data.get("results") or [])[:limit]]
    payload = {
        "query": text,
        "locale": locale,
        "rank_filter": rank,
        "total_results": data.get("total_results", 0),
        "results": results,
        "source": url,
        "fetched_at": _now(),
        "cached": False,
    }
    if use_cache:
        _write_cache("search", cache_key, payload)
    return payload


def get_taxon(
    taxon_id: int,
    locale: str = "zh-CN",
    *,
    use_cache: bool = True,
    ttl: float = DEFAULT_TTL,
) -> dict:
    try:
        identifier = int(taxon_id)
    except (TypeError, ValueError) as exc:
        raise InatError("taxon_id must be an integer") from exc
    params = {"locale": locale}
    cache_key = {"kind": "taxon", "id": identifier, **params}
    if use_cache:
        cached = _read_cache("taxon", cache_key, ttl)
        if cached is not None:
            cached["cached"] = True
            return cached
    url = f"{BASE_URL}/taxa/{identifier}?{urllib.parse.urlencode(params)}"
    data = _get_json(url)
    results = data.get("results") or []
    if not results:
        raise InatError(f"taxon {identifier} not found", 404)
    payload = normalize_taxon(results[0], fetched_at=_now(), cached=False)
    if use_cache:
        _write_cache("taxon", cache_key, payload)
    return payload


def load_aliases() -> dict[str, str]:
    aliases: dict[str, str] = {}
    for path in (ALIASES_EXAMPLE, ALIASES_LOCAL):
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict):
            aliases.update(
                {
                    str(key).strip(): str(value).strip()
                    for key, value in data.items()
                    if str(key).strip() and str(value).strip()
                }
            )
    return aliases


def _exact_match(results: list[dict], query: str) -> tuple[dict | None, str | None]:
    wanted = query.strip().casefold()
    for item in results:
        if item.get("is_active") is False:
            continue
        if (item.get("name") or "").strip().casefold() == wanted:
            return item, "scientific"
    for item in results:
        if item.get("is_active") is False:
            continue
        for field in ("common_name", "english_common_name"):
            if (item.get(field) or "").strip().casefold() == wanted:
                return item, field
    return None, None


def wikidata_candidates(name: str, limit: int = 3) -> list[dict]:
    params = {
        "action": "wbsearchentities",
        "search": name,
        "language": "zh",
        "uselang": "zh",
        "format": "json",
        "limit": max(1, min(limit, 10)),
        "type": "item",
    }
    url = f"{WIKIDATA_URL}?{urllib.parse.urlencode(params)}"
    data = _get_json(url)
    return [
        {
            "qid": hit.get("id"),
            "label": hit.get("label"),
            "description": hit.get("description"),
        }
        for hit in (data.get("search") or [])
        if hit.get("id")
    ]


def wikidata_taxon_name(qid: str) -> str | None:
    params = {"action": "wbgetentities", "ids": qid, "props": "claims", "format": "json"}
    url = f"{WIKIDATA_URL}?{urllib.parse.urlencode(params)}"
    data = _get_json(url)
    entity = (data.get("entities") or {}).get(qid) or {}
    for claim in ((entity.get("claims") or {}).get("P225") or []):
        value = ((claim.get("mainsnak") or {}).get("datavalue") or {}).get("value")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def wikidata_resolution(
    name: str,
    *,
    use_cache: bool = True,
    ttl: float = DEFAULT_TTL,
) -> dict:
    """Resolve a Chinese name via Wikidata to the first item carrying P225."""
    cache_key = {"kind": "wikidata", "name": name, "language": "zh"}
    if use_cache:
        cached = _read_cache("wikidata", cache_key, ttl)
        if cached is not None:
            cached["cached"] = True
            return cached
    payload: dict = {
        "name": name,
        "scientific_name": None,
        "qid": None,
        "label": None,
        "candidates": [],
        "cached": False,
    }
    for candidate in wikidata_candidates(name):
        description = (candidate.get("description") or "").casefold()
        if not any(token in description for token in ("species", "鸟", "种", "taxon")):
            continue
        scientific_name = wikidata_taxon_name(candidate["qid"])
        if not scientific_name:
            continue
        payload.update(
            {
                "scientific_name": scientific_name,
                "qid": candidate["qid"],
                "label": candidate.get("label"),
                "candidates": [candidate],
            }
        )
        break
    if use_cache:
        _write_cache("wikidata", cache_key, payload)
    return payload


def resolve_name(
    name: str,
    locale: str = "zh-CN",
    *,
    use_aliases: bool = True,
    allow_wikidata: bool = True,
    use_cache: bool = True,
) -> dict:
    """Resolve a Chinese or scientific name to a single verified taxon.

    Order: local alias -> scientific/exact iNat match -> Wikidata (P225) ->
    exact common-name match. Nothing is accepted on a fuzzy first hit.
    """
    original = (name or "").strip()
    if not original:
        raise InatError("name must not be empty")

    warnings: list[str] = []
    aliases = load_aliases() if use_aliases else {}
    alias_value = aliases.get(original)
    scientific = alias_value or (None if CJK.search(original) else original)
    via = "local-alias" if alias_value and alias_value != original else "query"

    if scientific:
        search = search_taxa(scientific, locale=locale, limit=10, use_cache=use_cache)
        match, field = _exact_match(search["results"], scientific)
        if match:
            taxon = get_taxon(int(match["id"]), locale=locale, use_cache=use_cache)
            return {
                "query": original,
                "resolved": True,
                "via": via,
                "matched_by": field,
                "scientific_name_used": scientific,
                "taxon": taxon,
                "candidates": [],
                "warnings": warnings,
            }
        warnings.append(f"iNaturalist has no exact active match for {scientific!r}")

    if allow_wikidata and CJK.search(original):
        wikidata = wikidata_resolution(original, use_cache=use_cache)
        scientific_name = wikidata.get("scientific_name")
        if scientific_name:
            search = search_taxa(scientific_name, locale=locale, limit=10, use_cache=use_cache)
            match, field = _exact_match(search["results"], scientific_name)
            if match:
                taxon = get_taxon(int(match["id"]), locale=locale, use_cache=use_cache)
                return {
                    "query": original,
                    "resolved": True,
                    "via": "wikidata",
                    "matched_by": field,
                    "scientific_name_used": scientific_name,
                    "wikidata": {
                        "qid": wikidata.get("qid"),
                        "label": wikidata.get("label"),
                        "cached": wikidata.get("cached"),
                    },
                    "taxon": taxon,
                    "candidates": [],
                    "warnings": warnings,
                }
            warnings.append(
                f"Wikidata suggested {scientific_name!r} but iNaturalist had no exact match"
            )

    fallback = search_taxa(original, locale=locale, limit=5, use_cache=use_cache)
    match, field = _exact_match(fallback["results"], original)
    if match:
        taxon = get_taxon(int(match["id"]), locale=locale, use_cache=use_cache)
        return {
            "query": original,
            "resolved": True,
            "via": "inat-common-name",
            "matched_by": field,
            "scientific_name_used": match.get("name"),
            "taxon": taxon,
            "candidates": [],
            "warnings": warnings,
        }
    warnings.append(
        "No exact match. iNaturalist free-text search returns fuzzy taxonomic noise "
        "for Chinese names; use a local alias or the scientific name."
    )
    return {
        "query": original,
        "resolved": False,
        "via": None,
        "matched_by": None,
        "scientific_name_used": None,
        "taxon": None,
        "candidates": fallback["results"],
        "total_results": fallback["total_results"],
        "warnings": warnings,
    }


def clear_cache() -> int:
    if not CACHE_DIR.is_dir():
        return 0
    removed = 0
    for path in CACHE_DIR.glob("*.json"):
        path.unlink(missing_ok=True)
        removed += 1
    return removed
