import unicodedata
from collections.abc import Iterable, Sequence


def normalized_lookup(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return "".join(character for character in normalized if character.isalnum())


def resolve_catalog_item(
    query: str | None,
    items: Iterable[dict],
    fields: Sequence[str],
) -> tuple[dict | None, list[str]]:
    if not query:
        return None, []
    key = normalized_lookup(query)
    if not key:
        return None, []
    prepared = []
    for item in items:
        labels = [str(item.get(field) or "") for field in fields]
        keys = [normalized_lookup(label) for label in labels if label]
        prepared.append((item, labels, keys))

    exact = [item for item, _labels, keys in prepared if key in keys]
    if len(exact) == 1:
        return exact[0], []
    contains = [
        item
        for item, _labels, keys in prepared
        if any(key in candidate or candidate in key for candidate in keys)
    ]
    unique = {item["id"]: item for item in contains}
    if len(unique) == 1:
        return next(iter(unique.values())), []

    candidates = exact if exact else list(unique.values())
    labels = [
        str(item.get(fields[0]) or item.get(fields[1]) or item.get("catalog_number") or item["id"])
        for item in candidates[:5]
    ]
    return None, labels
