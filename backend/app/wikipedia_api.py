"""Read-only Wikipedia summaries and distribution text.

The iNaturalist taxon detail deliberately carries only a very short Wikipedia
lead.  Subspecies ranges and descriptions live in the Wikipedia article body,
so this module fetches the plain-text extract through the public MediaWiki API.
It never edits Wikipedia, never scrapes HTML, and caches every successful
answer next to the iNaturalist cache.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

from .inat_mcp import inat_api

API_TEMPLATE = "https://{lang}.wikipedia.org/w/api.php"
USER_AGENT = inat_api.USER_AGENT
DEFAULT_TTL = 7 * 24 * 60 * 60.0
MAX_EXTRACT = 40_000
EXCERPT_LIMIT = 4_000
_LAST_REQUEST = 0.0
_HEADING = re.compile(r"^(={2,6})\s*(.+?)\s*\1\s*$", re.MULTILINE)
_RELEVANT = re.compile(
    r"亚种|分布|栖息|描述|特征|识别|生态|保护|分类|"
    r"subspecies|distribution|habitat|description|identification|taxonomy|conservation",
    re.IGNORECASE,
)


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _get_json(url: str, timeout: float = 8.0) -> dict:
    global _LAST_REQUEST
    delay = max(0, 1.05 - (time.monotonic() - _LAST_REQUEST))
    if delay:
        time.sleep(delay)
    _LAST_REQUEST = time.monotonic()
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read(4 * 1024 * 1024 + 1)
            if len(payload) > 4 * 1024 * 1024:
                raise RuntimeError("Wikipedia response too large")
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Wikipedia HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"Wikipedia network error: {exc}") from exc
    try:
        data = json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise RuntimeError("Wikipedia returned invalid JSON") from exc
    if not isinstance(data, dict):
        raise RuntimeError("Wikipedia returned an unexpected payload")
    return data


def title_from_url(url: str | None) -> tuple[str | None, str | None]:
    """Return ``(language, title)`` for a Wikipedia article URL."""
    if not url:
        return None, None
    parsed = urllib.parse.urlsplit(url)
    host = (parsed.hostname or "").casefold()
    if not host.endswith(".wikipedia.org"):
        return None, None
    lang = host.split(".", 1)[0]
    prefix = "/wiki/"
    if not parsed.path.startswith(prefix):
        return lang, None
    title = urllib.parse.unquote(parsed.path[len(prefix) :]).replace("_", " ")
    return lang, title.strip() or None


def _sections(text: str) -> list[tuple[str, str]]:
    matches = list(_HEADING.finditer(text))
    if not matches:
        return [("", text)]
    sections: list[tuple[str, str]] = []
    intro = text[: matches[0].start()].strip()
    if intro:
        sections.append(("", intro))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[match.end() : end].strip()
        sections.append((match.group(2).strip(), body))
    return sections


def excerpt_for_ai(text: str, limit: int = EXCERPT_LIMIT) -> str:
    """Keep the sections that actually help a subspecies decision."""
    if not text:
        return ""
    picked: list[str] = []
    used = 0
    for heading, body in _sections(text):
        relevant = bool(heading and _RELEVANT.search(heading))
        if heading and not relevant:
            continue
        if not heading and len(body) > 800:
            body = body[:800].rstrip() + "…"
        block = f"## {heading}\n{body}" if heading else body
        if used + len(block) > limit:
            remaining = max(0, limit - used)
            if remaining > 200:
                picked.append(block[:remaining].rstrip() + "…")
            break
        picked.append(block)
        used += len(block)
    if not picked:
        return text[:limit].rstrip() + ("…" if len(text) > limit else "")
    return "\n\n".join(picked)[:limit]


def _page_title(pages: object) -> dict | None:
    if isinstance(pages, list):
        return pages[0] if pages and isinstance(pages[0], dict) else None
    if isinstance(pages, dict):
        first = next(iter(pages.values()), None)
        return first if isinstance(first, dict) else None
    return None


def _fetch_one(lang: str, title: str, *, use_cache: bool, ttl: float) -> dict | None:
    cache_key = {"kind": "wiki", "lang": lang, "title": title}
    if use_cache:
        cached = inat_api._read_cache("wiki", cache_key, ttl)
        if cached is not None:
            cached["cached"] = True
            return cached
    params = {
        "action": "query",
        "prop": "extracts",
        "explaintext": "1",
        "redirects": "1",
        "format": "json",
        "formatversion": "2",
        "titles": title,
    }
    if lang == "zh":
        params["variant"] = "zh-cn"
    url = f"{API_TEMPLATE.format(lang=lang)}?{urllib.parse.urlencode(params)}"
    data = _get_json(url)
    page = _page_title((data.get("query") or {}).get("pages"))
    if not page or page.get("missing"):
        return None
    extract = page.get("extract") or ""
    if not isinstance(extract, str) or not extract.strip():
        return None
    extract = extract[:MAX_EXTRACT]
    resolved_title = page.get("title") or title
    payload = {
        "available": True,
        "lang": lang,
        "title": resolved_title,
        "url": f"https://{lang}.wikipedia.org/wiki/"
        + urllib.parse.quote(resolved_title.replace(" ", "_")),
        "extract": extract,
        "excerpt": excerpt_for_ai(extract),
        "chars": len(extract),
        "source": url,
        "fetched_at": _now(),
        "cached": False,
    }
    if use_cache:
        inat_api._write_cache("wiki", cache_key, payload)
    return payload


def fetch_extract(
    *,
    url: str | None = None,
    title: str | None = None,
    lang: str = "zh",
    fallback_titles: tuple[str, ...] = (),
    use_cache: bool = True,
    ttl: float = DEFAULT_TTL,
) -> dict:
    """Fetch a plain-text article, trying an English fallback when needed."""
    candidates: list[tuple[str, str]] = []
    url_lang, url_title = title_from_url(url)
    if url_title:
        candidates.append((url_lang or lang, url_title))
    if title:
        candidates.append((lang, title.strip()))
    for fallback in fallback_titles:
        if fallback and fallback.strip():
            candidates.append(("en", fallback.strip()))
    seen: set[tuple[str, str]] = set()
    tried: list[str] = []
    for candidate_lang, candidate_title in candidates:
        key = (candidate_lang, candidate_title)
        if key in seen:
            continue
        seen.add(key)
        tried.append(f"{candidate_lang}:{candidate_title}")
        try:
            payload = _fetch_one(
                candidate_lang,
                candidate_title,
                use_cache=use_cache,
                ttl=ttl,
            )
        except RuntimeError:
            continue
        if payload is not None:
            payload["tried"] = tried
            return payload
    return {
        "available": False,
        "message": "维基百科暂无可用条目，已保留 iNaturalist 资料。",
        "tried": tried,
        "fetched_at": _now(),
    }
