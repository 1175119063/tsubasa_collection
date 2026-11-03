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
import os
import pathlib
import re
import tempfile
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime

BASE_URL = "https://api.inaturalist.org/v1"
WIKIDATA_URL = "https://www.wikidata.org/w/api.php"
USER_AGENT = "Tsubasa/0.3 (personal bird journal; read-only taxonomy lookup)"
LAB_DIR = pathlib.Path(__file__).resolve().parent
CACHE_DIR = pathlib.Path(os.environ.get("TSUBASA_INAT_CACHE_DIR", LAB_DIR / "cache"))
ALIASES_DIR = pathlib.Path(os.environ.get("TSUBASA_INAT_ALIASES_DIR", LAB_DIR))
ALIASES_LOCAL = ALIASES_DIR / "aliases.local.json"
ALIASES_EXAMPLE = ALIASES_DIR / "aliases.example.json"
DEFAULT_TTL = 7 * 24 * 60 * 60.0
NEARBY_TTL = 6 * 60 * 60.0
CJK = re.compile(r"[\u3400-\u9fff]")
HTML_TAG = re.compile(r"<[^>]+>")


class InatError(RuntimeError):
    """A lookup failed (network, upstream status, or unusable payload)."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


def configure(
    cache_dir: pathlib.Path | str,
    aliases_dir: pathlib.Path | str | None = None,
) -> None:
    """Point the shared source layer at the application's data directory."""
    global CACHE_DIR, ALIASES_DIR, ALIASES_LOCAL, ALIASES_EXAMPLE
    CACHE_DIR = pathlib.Path(cache_dir)
    if aliases_dir is not None:
        ALIASES_DIR = pathlib.Path(aliases_dir)
        ALIASES_LOCAL = ALIASES_DIR / "aliases.local.json"
        ALIASES_EXAMPLE = ALIASES_DIR / "aliases.example.json"


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


_deadline: ContextVar[float | None] = ContextVar("inat_deadline", default=None)
_last_request = 0.0


@contextmanager
def request_budget(seconds: float = 40):
    token = _deadline.set(time.monotonic() + seconds)
    try:
        yield
    finally:
        _deadline.reset(token)


def _get_json(url: str, timeout: float = 8.0) -> dict:
    global _last_request
    # Stay below one upstream request per second, including multi-step resolution.
    delay = max(0, 1.05 - (time.monotonic() - _last_request))
    deadline = _deadline.get()
    if deadline is not None:
        remaining = deadline - time.monotonic() - delay
        if remaining <= 0:
            raise InatError("查询超时，请稍后重试或改用学名")
        timeout = min(timeout, remaining)
    if delay:
        time.sleep(delay)
    _last_request = time.monotonic()
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read(4 * 1024 * 1024 + 1)
            if len(payload) > 4 * 1024 * 1024:
                raise InatError("upstream response too large")
    except urllib.error.HTTPError as exc:
        detail = exc.read()[:300].decode("utf-8", "replace")
        if exc.code == 429:
            raise InatError("资料来源请求过于频繁，请稍后重试", 429) from exc
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
    return f"v3-{kind}-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]}"


def _read_cache(kind: str, params: dict, ttl: float) -> dict | None:
    path = CACHE_DIR / f"{_cache_key(kind, params)}.json"
    try:
        if not path.is_file() or time.time() - path.stat().st_mtime > ttl:
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _write_cache(kind: str, params: dict, payload: dict) -> None:
    temporary = None
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path = CACHE_DIR / f"{_cache_key(kind, params)}.json"
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=CACHE_DIR, suffix=".tmp", delete=False
        ) as stream:
            temporary = pathlib.Path(stream.name)
            json.dump(payload, stream, ensure_ascii=False)
        temporary.replace(path)
        files = sorted(CACHE_DIR.glob("*.json"), key=lambda item: item.stat().st_mtime)
        for old in files[:-512]:
            old.unlink(missing_ok=True)
    except OSError:
        pass  # A read-only or full cache must not discard a successful lookup.
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


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
        "is_bird": item.get("iconic_taxon_name") == "Aves"
        or any(entry.get("name") == "Aves" for entry in (item.get("ancestors") or [])),
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


def _compact_child(item: dict) -> dict:
    photo = item.get("default_photo") or {}
    return {
        "id": item.get("id"),
        "name": item.get("name"),
        "common_name": item.get("preferred_common_name") or item.get("common_name"),
        "english_common_name": item.get("english_common_name"),
        "rank": item.get("rank"),
        "is_active": item.get("is_active"),
        "observations_count": item.get("observations_count"),
        "url": _taxon_url(item.get("id")),
        "photo": {
            "attribution": photo.get("attribution"),
            "license": photo.get("license_code"),
            "url": photo.get("medium_url") or photo.get("url"),
        }
        if photo
        else None,
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
            place = entry.get("place") or {}
            conservation.append(
                {
                    "status": entry.get("status"),
                    "authority": entry.get("authority"),
                    "place": place.get("name"),
                    "place_id": place.get("id"),
                    "place_display_name": place.get("display_name"),
                    "admin_level": place.get("admin_level"),
                    "iucn": entry.get("iucn"),
                    "url": entry.get("url"),
                    "description": _strip_html(entry.get("description")),
                    "geoprivacy": entry.get("geoprivacy"),
                    "updated_at": entry.get("updated_at"),
                }
            )
    children = [
        _compact_child(entry)
        for entry in (item.get("children") or [])
        if entry.get("id") and entry.get("is_active") is not False
    ]
    photo = item.get("default_photo") or {}
    taxon_id = item.get("id")
    return {
        "id": taxon_id,
        "name": item.get("name"),
        "common_name": item.get("preferred_common_name"),
        "english_common_name": item.get("english_common_name"),
        "rank": item.get("rank"),
        "is_bird": item.get("iconic_taxon_name") == "Aves"
        or any(entry.get("name") == "Aves" for entry in ancestors),
        "is_active": item.get("is_active"),
        "extinct": item.get("extinct"),
        "complete_rank": item.get("complete_rank"),
        "children_count": item.get("children_count", len(children)),
        "children": children,
        "listed_taxa_count": item.get("listed_taxa_count"),
        "vision": item.get("vision"),
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
    params = {"q": text, "locale": locale, "per_page": limit, "iconic_taxa": "Aves"}
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
    if type(taxon_id) is not int or taxon_id <= 0:
        raise InatError("taxon_id must be a positive integer")
    identifier = taxon_id
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
    if results[0].get("id") != identifier:
        raise InatError("资料来源返回了不同的物种编号")
    payload = normalize_taxon(results[0], fetched_at=_now(), cached=False)
    payload["source_url"] = url
    if use_cache:
        _write_cache("taxon", cache_key, payload)
    return payload


def get_taxon_children(
    taxon_id: int,
    locale: str = "zh-CN",
    *,
    use_cache: bool = True,
    ttl: float = DEFAULT_TTL,
) -> dict:
    """Return the active subspecies under a species in one bounded request."""
    if type(taxon_id) is not int or taxon_id <= 0:
        raise InatError("taxon_id must be a positive integer")
    params = {
        "parent_id": taxon_id,
        "rank": "subspecies",
        "per_page": 30,
        "locale": locale,
    }
    cache_key = {"kind": "children", "id": taxon_id, "locale": locale}
    if use_cache:
        cached = _read_cache("children", cache_key, ttl)
        if cached is not None:
            cached["cached"] = True
            return cached
    url = f"{BASE_URL}/taxa?{urllib.parse.urlencode(params)}"
    data = _get_json(url)
    results = [
        _compact_child(item)
        for item in (data.get("results") or [])[:30]
        if item.get("id") and item.get("is_active") is not False
    ]
    payload = {
        "taxon_id": taxon_id,
        "locale": locale,
        "total_results": data.get("total_results", len(results)),
        "results": results,
        "source": url,
        "fetched_at": _now(),
        "cached": False,
    }
    if use_cache:
        _write_cache("children", cache_key, payload)
    return payload


def nearby_subspecies(
    taxon_id: int,
    latitude: float,
    longitude: float,
    radius_km: int = 50,
    *,
    use_cache: bool = True,
    ttl: float = NEARBY_TTL,
) -> dict:
    """Count research-grade nearby records that are identified to subspecies.

    iNaturalist cannot group `species_counts` by subspecies, so this reads one
    bounded page of observations and counts locally. It is evidence about what
    local identifiers have recorded, not proof that other subspecies are absent.
    """
    if type(taxon_id) is not int or taxon_id <= 0:
        raise InatError("taxon_id must be a positive integer")
    if isinstance(latitude, bool) or not isinstance(latitude, (int, float)):
        raise InatError("latitude must be a number")
    if isinstance(longitude, bool) or not isinstance(longitude, (int, float)):
        raise InatError("longitude must be a number")
    if not -90 <= latitude <= 90:
        raise InatError("latitude must be between -90 and 90")
    if not -180 <= longitude <= 180:
        raise InatError("longitude must be between -180 and 180")
    if isinstance(radius_km, bool) or not isinstance(radius_km, int):
        raise InatError("radius_km must be an integer")
    radius_km = max(1, min(radius_km, 500))
    params = {
        "taxon_id": taxon_id,
        "hrank": "subspecies",
        "lrank": "subspecies",
        "lat": round(float(latitude), 5),
        "lng": round(float(longitude), 5),
        "radius": radius_km,
        "per_page": 200,
        "order_by": "observed_on",
        "locale": "zh-CN",
    }
    cache_key = {
        "kind": "nearby",
        "id": taxon_id,
        "lat": round(float(latitude), 4),
        "lng": round(float(longitude), 4),
        "radius": radius_km,
    }
    if use_cache:
        cached = _read_cache("nearby", cache_key, ttl)
        if cached is not None:
            cached["cached"] = True
            return cached
    url = f"{BASE_URL}/observations?{urllib.parse.urlencode(params)}"
    data = _get_json(url)
    results = data.get("results") or []
    counts: dict[int, dict] = {}
    for observation in results:
        taxon = observation.get("taxon") or {}
        entry_id = taxon.get("id")
        if not isinstance(entry_id, int):
            continue
        entry = counts.setdefault(
            entry_id,
            {
                "taxon_id": entry_id,
                "name": taxon.get("name"),
                "common_name": taxon.get("preferred_common_name"),
                "rank": taxon.get("rank"),
                "count": 0,
            },
        )
        entry["count"] += 1
    payload = {
        "taxon_id": taxon_id,
        "latitude": round(float(latitude), 5),
        "longitude": round(float(longitude), 5),
        "radius_km": radius_km,
        "total_results": data.get("total_results", len(results)),
        "returned": len(results),
        "truncated": data.get("total_results", len(results)) > len(results),
        "counts": sorted(counts.values(), key=lambda item: item["count"], reverse=True),
        "source": url,
        "fetched_at": _now(),
        "cached": False,
    }
    if use_cache:
        _write_cache("nearby", cache_key, payload)
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


def _name_key(value: str) -> str:
    return unicodedata.normalize("NFKC", value).strip().casefold()


def _exact_match(results: list[dict], query: str) -> tuple[dict | None, str | None]:
    wanted = _name_key(query)
    for fields in (("name",), ("common_name", "english_common_name")):
        matches = {}
        for item in results:
            if item.get("is_active") is not True or not item.get("id"):
                continue
            for field in fields:
                if _name_key(item.get(field) or "") == wanted:
                    matches[item["id"]] = (item, "scientific" if field == "name" else field)
        if matches:
            return next(iter(matches.values())) if len(matches) == 1 else (None, None)
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
            "matched_text": (hit.get("match") or {}).get("text"),
            "aliases": hit.get("aliases") or [],
        }
        for hit in (data.get("search") or [])
        if hit.get("id")
    ]


def wikidata_taxon_name(qid: str) -> str | None:
    params = {"action": "wbgetentities", "ids": qid, "props": "claims", "format": "json"}
    url = f"{WIKIDATA_URL}?{urllib.parse.urlencode(params)}"
    data = _get_json(url)
    entity = (data.get("entities") or {}).get(qid) or {}
    names = set()
    for claim in (entity.get("claims") or {}).get("P225") or []:
        if claim.get("rank") == "deprecated":
            continue
        value = ((claim.get("mainsnak") or {}).get("datavalue") or {}).get("value")
        if isinstance(value, str) and value.strip():
            names.add(value.strip())
    return next(iter(names)) if len(names) == 1 else None


def wikidata_resolution(
    name: str,
    *,
    use_cache: bool = True,
    ttl: float = DEFAULT_TTL,
) -> dict:
    """Require an exact label/alias and a unique P225-bearing candidate."""
    cache_key = {"kind": "wikidata", "name": name, "language": "zh"}
    if use_cache:
        cached = _read_cache("wikidata", cache_key, ttl)
        if cached is not None:
            cached["cached"] = True
            return cached
    payload: dict = {
        "name": name,
        "fetched_at": _now(),
        "source_url": WIKIDATA_URL,
        "scientific_name": None,
        "qid": None,
        "label": None,
        "candidates": [],
        "cached": False,
    }
    matches = []
    for candidate in wikidata_candidates(name):
        labels = [
            candidate.get("label"),
            candidate.get("matched_text"),
            *(candidate.get("aliases") or []),
        ]
        if not any(
            isinstance(label, str) and _name_key(label) == _name_key(name) for label in labels
        ):
            continue
        scientific_name = wikidata_taxon_name(candidate["qid"])
        if scientific_name:
            matches.append({**candidate, "scientific_name": scientific_name})
    payload["candidates"] = matches
    unique = {item["qid"]: item for item in matches}
    if len(unique) == 1:
        candidate = next(iter(unique.values()))
        payload.update(
            scientific_name=candidate["scientific_name"],
            qid=candidate["qid"],
            label=candidate.get("label"),
            source_url=f"https://www.wikidata.org/wiki/{candidate['qid']}",
        )
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
    """Resolve unique names, or retain plausible candidates for human selection."""
    original = (name or "").strip()
    if not original:
        raise InatError("name must not be empty")
    warnings: list[str] = []

    def search(text):
        return search_taxa(text, locale=locale, limit=10, rank="species", use_cache=use_cache)

    def resolved(match, field, via, scientific, wikidata=None):
        return {
            "query": original,
            "resolved": True,
            "via": via,
            "matched_by": field,
            "scientific_name_used": scientific,
            "taxon": get_taxon(match["id"], locale=locale, use_cache=use_cache),
            "candidates": [],
            "warnings": warnings,
            "wikidata": wikidata,
        }

    def unresolved(candidates):
        warnings.append("没有唯一准确匹配，请核对候选的学名；也可以输入完整学名重试。")
        return {
            "query": original,
            "resolved": False,
            "via": None,
            "matched_by": None,
            "scientific_name_used": None,
            "taxon": None,
            "warnings": warnings,
            "candidates": list({item["id"]: item for item in candidates}.values()),
        }

    aliases = load_aliases() if use_aliases else {}
    scientific = aliases.get(original) or (None if CJK.search(original) else original)
    if scientific:
        found = search(scientific)
        match, field = _exact_match(found["results"], scientific)
        if match:
            via = "local-alias" if original in aliases else "query"
            return resolved(match, field, via, scientific)
        if not CJK.search(original):
            return unresolved(found["results"])
        warnings.append(f"别名对应的 {scientific!r} 没有唯一匹配，已尝试其他来源。")

    ambiguous = False
    if allow_wikidata and CJK.search(original):
        try:
            wikidata = wikidata_resolution(original, use_cache=use_cache)
        except InatError:
            warnings.append("Wikidata 暂时不可用，已尝试直接查询 iNaturalist。")
            wikidata = {}
        ambiguous = len(wikidata.get("candidates", [])) > 1
        if ambiguous:
            warnings.append("Wikidata 存在多个同名条目，已分别查询学名，请选择候选。")
        candidates = []
        for candidate in wikidata.get("candidates", [])[:3]:
            scientific = candidate["scientific_name"]
            found = search(scientific)
            match, field = _exact_match(found["results"], scientific)
            provenance = {
                "qid": candidate["qid"],
                "label": candidate.get("label"),
                "source_url": f"https://www.wikidata.org/wiki/{candidate['qid']}",
                "cached": wikidata.get("cached"),
                "fetched_at": wikidata.get("fetched_at"),
            }
            if match and not ambiguous:
                return resolved(match, field, "wikidata", scientific, provenance)
            # Keep both exact scientific candidates when Chinese names overlap.
            candidates.extend(
                {**item, "name_source": provenance}
                for item in found["results"]
                if _name_key(item.get("name") or "") == _name_key(scientific)
            )
        if candidates:
            return unresolved(candidates)

    fallback = search(original)
    match, field = _exact_match(fallback["results"], original)
    if match and not ambiguous:
        return resolved(match, field, "inat-common-name", match.get("name"))
    return unresolved(fallback["results"])


def clear_cache() -> int:
    if not CACHE_DIR.is_dir():
        return 0
    removed = 0
    for path in CACHE_DIR.glob("*.json"):
        path.unlink(missing_ok=True)
        removed += 1
    return removed
