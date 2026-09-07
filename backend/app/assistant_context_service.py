from __future__ import annotations

import json

from .assistant_catalog import normalized_lookup
from .database import Database
from .media_store import MediaStore
from .services import BirdService


class AssistantLibraryContextService:
    """Build the bounded, read-only local-library context used by assistant chat."""

    PROJECT_TERMS = (
        "记录",
        "观察",
        "物种",
        "鸟种",
        "图鉴",
        "收集",
        "资料库",
        "地点",
        "区域",
        "远征",
        "多少",
        "几笔",
        "几种",
    )

    def __init__(self, database: Database, media_store: MediaStore) -> None:
        self.database = database
        self.media_store = media_store

    def build(self, question: str) -> str | None:
        if not any(term in question for term in self.PROJECT_TERMS):
            return None
        query = normalized_lookup(question)
        with self.database.session_factory() as session:
            service = BirdService(session, self.media_store)
            context = self._context(service, question, query)
        return json.dumps(context, ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _matches(item: dict, fields: tuple[str, ...], query: str) -> bool:
        return any(
            (needle := normalized_lookup(str(item.get(field) or "")))
            and needle in query
            for field in fields
        )

    def _context(self, service: BirdService, question: str, query: str) -> dict:
        stats = service.stats()
        species = service.list_species()
        locations = service.list_locations()
        trips = service.list_trips()
        matched_species = [
            item
            for item in species
            if self._matches(
                item,
                ("chinese_name", "scientific_name", "catalog_number"),
                query,
            )
        ][:3]
        matched_locations = [
            item
            for item in locations
            if self._matches(
                item,
                ("name", "catalog_number", "city", "district"),
                query,
            )
        ][:3]
        matched_trips = [
            item
            for item in trips
            if self._matches(item, ("name", "catalog_number"), query)
        ][:3]
        include_records = any(
            term in question for term in ("哪些", "列出", "分别", "时间", "日期")
        )
        species_context = []
        for item in matched_species:
            entry = {
                "catalog_number": item["catalog_number"],
                "chinese_name": item["chinese_name"],
                "scientific_name": item["scientific_name"],
                "observation_count": item["observation_count"],
            }
            if include_records:
                detail = service.species_detail(item["id"])
                entry["records"] = [
                    {
                        "id": record["id"],
                        "observed_at": record["observed_at"],
                        "admin1_name": record["admin1_name"],
                        "locality": record["locality"],
                    }
                    for record in detail["observations"][:20]
                ]
            species_context.append(entry)
        return {
            "source": "翼·时光记当前数据库的只读即时摘要",
            "totals": stats,
            "matched_species": species_context,
            "matched_locations": [
                {
                    "catalog_number": item["catalog_number"],
                    "name": item["name"],
                    "observation_count": item["observation_count"],
                    "species_count": item["species_count"],
                    "trip_count": item["trip_count"],
                }
                for item in matched_locations
            ],
            "matched_trips": [
                {
                    "catalog_number": item["catalog_number"],
                    "name": item["name"],
                    "observation_count": item["observation_count"],
                    "species_count": item["species_count"],
                    "location_count": item["location_count"],
                }
                for item in matched_trips
            ],
        }
