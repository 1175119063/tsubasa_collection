from __future__ import annotations

import re
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

from .assistant_schemas import AssistantSqlQuery


class ObservationQueryError(RuntimeError):
    pass


@dataclass(frozen=True)
class ObservationQueryResult:
    observation_ids: list[int]
    truncated: bool


VIEW_DEFINITIONS = (
    """
    CREATE TEMP VIEW field_observations AS
    SELECT
        o.id AS observation_id,
        o.observed_at AS observed_at,
        date(o.observed_at) AS observed_date,
        CAST(strftime('%Y', o.observed_at) AS INTEGER) AS observed_year,
        CAST(strftime('%m', o.observed_at) AS INTEGER) AS observed_month,
        CAST(strftime('%d', o.observed_at) AS INTEGER) AS observed_day,
        o.season AS season,
        o.locality AS locality,
        o.country_name AS country_name,
        o.admin1_name AS admin1_name,
        o.notes AS observation_notes,
        oll.location_id AS location_id,
        bl.name AS location_name,
        bl.city AS location_city,
        bl.district AS location_district,
        otl.trip_id AS trip_id,
        COALESCE(bt.name, primary_location.name) AS trip_name,
        COUNT(os.id) AS species_count
    FROM observations o
    JOIN observation_species os ON os.observation_id = o.id
    LEFT JOIN observation_location_links oll ON oll.observation_id = o.id
    LEFT JOIN birding_locations bl ON bl.id = oll.location_id
    LEFT JOIN observation_trip_links otl ON otl.observation_id = o.id
    LEFT JOIN birding_trips bt ON bt.id = otl.trip_id
    LEFT JOIN birding_locations primary_location ON primary_location.id = bt.location_id
    GROUP BY o.id
    """,
    """
    CREATE TEMP VIEW field_observation_taxa AS
    SELECT
        os.observation_id AS observation_id,
        s.id AS species_id,
        printf('AV-%06d', s.id) AS catalog_number,
        s.chinese_name AS species_chinese_name,
        s.scientific_name AS species_scientific_name,
        g.chinese_name AS genus_chinese_name,
        g.scientific_name AS genus_scientific_name,
        f.chinese_name AS family_chinese_name,
        f.scientific_name AS family_scientific_name,
        tax_order.chinese_name AS order_chinese_name,
        tax_order.scientific_name AS order_scientific_name,
        sub.chinese_name AS subspecies_chinese_name,
        sub.scientific_name AS subspecies_scientific_name,
        os.photo_type AS photo_type,
        os.sex AS sex,
        os.life_stage AS life_stage,
        os.notes AS species_notes,
        os.is_primary AS is_primary
    FROM observation_species os
    JOIN species s ON s.id = os.species_id
    JOIN genera g ON g.id = s.genus_id
    JOIN families f ON f.id = g.family_id
    JOIN taxonomic_orders tax_order ON tax_order.id = f.order_id
    LEFT JOIN subspecies sub ON sub.id = os.subspecies_id
    """,
)

PUBLIC_VIEWS = {"field_observations", "field_observation_taxa"}
PRIVATE_TABLES = {
    "observations",
    "observation_species",
    "species",
    "genera",
    "families",
    "taxonomic_orders",
    "subspecies",
    "observation_location_links",
    "birding_locations",
    "observation_trip_links",
    "birding_trips",
    "media_assets",
}
_FIRST_KEYWORD = re.compile(r"^\s*(?:WITH\b|SELECT\b)", re.IGNORECASE)
_BANNED = re.compile(
    r"\b(?:INSERT|UPDATE|DELETE|REPLACE|DROP|ALTER|CREATE|ATTACH|DETACH|PRAGMA|VACUUM|"
    r"REINDEX|ANALYZE|LOAD_EXTENSION)\b",
    re.IGNORECASE,
)
_TABLE_REFERENCE = re.compile(r"\b(?:FROM|JOIN)\s+([A-Za-z_][A-Za-z0-9_]*)", re.IGNORECASE)
_CTE_NAME = re.compile(r"(?:\bWITH|,)\s*([A-Za-z_][A-Za-z0-9_]*)\s+AS\s*\(", re.IGNORECASE)


class ObservationQueryExecutor:
    """Runs model-authored SELECTs in a read-only, view-limited SQLite connection."""

    def __init__(self, database_path: Path, row_limit: int = 500) -> None:
        self.database_path = database_path
        self.row_limit = row_limit

    def execute(self, plan: AssistantSqlQuery) -> ObservationQueryResult:
        sql = plan.sql.strip().rstrip(";").strip()
        if not _FIRST_KEYWORD.match(sql) or _BANNED.search(sql) or ";" in sql:
            raise ObservationQueryError("查询计划包含不允许的数据库操作")
        if "observation_id" not in sql.casefold():
            raise ObservationQueryError("查询必须返回 observation_id")
        sql_words = {word.casefold() for word in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", sql)}
        if sql_words & PRIVATE_TABLES:
            raise ObservationQueryError("查询不能直接访问资料库底层表")
        cte_names = {match.casefold() for match in _CTE_NAME.findall(sql)}
        referenced = {match.casefold() for match in _TABLE_REFERENCE.findall(sql)}
        if not referenced or not referenced.issubset(PUBLIC_VIEWS | cte_names):
            raise ObservationQueryError("查询只能访问田野记录 skill 的只读视图")

        uri = f"file:{self.database_path.as_posix()}?mode=ro"
        connection = sqlite3.connect(uri, uri=True, timeout=5)
        connection.row_factory = sqlite3.Row
        try:
            for definition in VIEW_DEFINITIONS:
                connection.execute(definition)
            connection.execute("PRAGMA query_only = ON")
            deadline = time.monotonic() + 2
            connection.set_progress_handler(
                lambda: 1 if time.monotonic() > deadline else 0,
                1000,
            )
            connection.set_authorizer(self._authorizer)
            wrapped = f"SELECT DISTINCT observation_id FROM ({sql}) LIMIT {self.row_limit + 1}"
            try:
                rows = connection.execute(wrapped, plan.parameters).fetchall()
            except sqlite3.Error as exc:
                raise ObservationQueryError(f"无法执行生成的查询：{exc}") from exc
        finally:
            connection.close()

        identifiers: list[int] = []
        for row in rows[: self.row_limit]:
            try:
                identifiers.append(int(row["observation_id"]))
            except (KeyError, TypeError, ValueError) as exc:
                raise ObservationQueryError("查询结果中的 observation_id 无效") from exc
        return ObservationQueryResult(list(dict.fromkeys(identifiers)), len(rows) > self.row_limit)

    @staticmethod
    def _authorizer(
        action: int,
        arg1: str | None,
        arg2: str | None,
        _db: str | None,
        source: str | None,
    ) -> int:
        allowed_actions = {
            sqlite3.SQLITE_SELECT,
            sqlite3.SQLITE_READ,
            sqlite3.SQLITE_FUNCTION,
            sqlite3.SQLITE_RECURSIVE,
        }
        if action not in allowed_actions:
            return sqlite3.SQLITE_DENY
        if action == sqlite3.SQLITE_READ:
            table = str(arg1 or "").casefold()
            origin = str(source or "").casefold()
            column = str(arg2 or "")
            if table not in PUBLIC_VIEWS and origin not in PUBLIC_VIEWS and column:
                return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK


QUERY_SKILL_SCHEMA = """只可查询下面两个只读视图。SQL 必须返回名为 observation_id 的列。

field_observations（一行一笔拍摄记录）：
- observation_id, observed_at, observed_date, observed_year, observed_month, observed_day
- season, locality, country_name, admin1_name, observation_notes
- location_id, location_name, location_city, location_district
- trip_id, trip_name, species_count

field_observation_taxa（一行是照片中的一个物种）：
- observation_id, species_id, catalog_number
- species_chinese_name, species_scientific_name
- genus_chinese_name, genus_scientific_name
- family_chinese_name, family_scientific_name
- order_chinese_name, order_scientific_name
- subspecies_chinese_name, subspecies_scientific_name
- photo_type, sex, life_stage, species_notes, is_primary

查询规则：
1. 只能生成一条参数化 SELECT 或 WITH ... SELECT；禁止任何写操作、PRAGMA 和数据库结构操作。
2. SQL 最终必须返回 observation_id；需要去重时使用 DISTINCT。
3. 用户说“A和B的所有记录”通常表示并集，用 IN 或 OR；“同时拍到/同框”才用 GROUP BY 与 HAVING。
4. 精确到日的日期使用 observed_date；日期范围采用左闭右开或明确的 BETWEEN。
5. “某科/某目/某属”使用对应分类字段；“名称含有某字”才使用 LIKE。
6. 所有用户提供的值必须放在 parameters 中并使用 :name 占位符，不得直接拼入 SQL。
7. 不要擅自添加排序含义。sort 只控制页面展示顺序，未说明时使用 desc。
8. interpretation 用简短中文说明你实际采用的查询含义；有歧义时在 warnings 中说明。

典型语义：
- “2024年4月5日的全部记录”：在 field_observations 中令 observed_date = :day。
- “白头鹎和灰喜鹊的所有记录”：在 field_observation_taxa 中令 species_chinese_name
  IN (:species_1, :species_2)，这是并集，不要求同框。
- “同时拍到白头鹎和灰喜鹊”：按 observation_id 分组，并用
  HAVING COUNT(DISTINCT species_chinese_name) = 2 保证同一笔观察同时命中。
- “鸦科的记录”：查询 family_chinese_name = :family_name，不要改写为某一个物种。
- “所有名字中带鹭的记录”：查询 species_chinese_name LIKE :pattern，参数值为“%鹭%”。
"""
