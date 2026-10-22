"""Probe how iNaturalist handles Chinese common names.

The script file is UTF-8, so the Chinese literals are sent to the API correctly
(piping Chinese through the PowerShell stdin of python.exe corrupts them).
"""

from __future__ import annotations

import json
import pathlib
import urllib.parse
import urllib.request

UA = {"User-Agent": "Tsubasa-MCP-Lab/0.1 (local experiment)"}
HERE = pathlib.Path(__file__).parent
FIXTURES = HERE / "fixtures"
FIXTURES.mkdir(exist_ok=True)


def fetch(url: str) -> dict:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as response:
        return json.load(response)


def inat(params: dict) -> dict:
    return fetch("https://api.inaturalist.org/v1/taxa?" + urllib.parse.urlencode(params))


report: dict[str, object] = {}
for label, params in (
    ("zh_common", {"q": "灰翅浮鸥", "locale": "zh-CN", "per_page": 3}),
    ("zh_common_2", {"q": "白鹭", "locale": "zh-CN", "per_page": 3}),
    ("zh_partial", {"q": "浮鸥", "locale": "zh-CN", "per_page": 3}),
    ("sci", {"q": "Chlidonias hybrida", "locale": "zh-CN", "per_page": 3}),
):
    data = inat(params)
    report[label] = data
    rows = [
        {
            "id": item.get("id"),
            "name": item.get("name"),
            "common": item.get("preferred_common_name"),
            "rank": item.get("rank"),
        }
        for item in data.get("results", [])[:3]
    ]
    print(f"{label}: total={data.get('total_results')} rows={json.dumps(rows, ensure_ascii=True)}")

wiki = fetch(
    "https://zh.wikipedia.org/w/api.php?"
    + urllib.parse.urlencode(
        {"action": "query", "list": "search", "srsearch": "灰翅浮鸥", "format": "json", "srlimit": 3}
    )
)
report["wikipedia"] = wiki
print("wikipedia hits:", [hit.get("title") for hit in wiki.get("query", {}).get("search", [])])

wikidata = fetch(
    "https://www.wikidata.org/w/api.php?"
    + urllib.parse.urlencode(
        {
            "action": "wbsearchentities",
            "search": "灰翅浮鸥",
            "language": "zh",
            "uselang": "zh",
            "format": "json",
            "limit": 3,
        }
    )
)
report["wikidata"] = wikidata
print(
    "wikidata hits:",
    [
        (hit.get("id"), hit.get("label"), hit.get("description"))
        for hit in wikidata.get("search", [])
    ],
)

(FIXTURES / "zh_probe.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
)
