"""Make observation species and cover photo single-source."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text

revision = "20261104_10"
down_revision = "20261022_09"
branch_labels = None
depends_on = None

_OLD_COLUMNS = (
    "species_id",
    "subspecies_id",
    "photo_asset_id",
    "photo_type",
    "sex",
    "life_stage",
)

_PRIMARY_MISSING = """
SELECT COUNT(*) FROM observations o
WHERE (
    SELECT COUNT(*) FROM observation_species e
    WHERE e.observation_id = o.id AND e.is_primary = 1
) != 1
"""

_PRIMARY_MISMATCH = """
SELECT COUNT(*) FROM observations o
JOIN observation_species e
  ON e.observation_id = o.id AND e.is_primary = 1
WHERE o.species_id IS NOT e.species_id
   OR o.subspecies_id IS NOT e.subspecies_id
   OR o.photo_type IS NOT e.photo_type
   OR o.sex IS NOT e.sex
   OR o.life_stage IS NOT e.life_stage
"""

_COVER_MISSING = """
SELECT COUNT(*) FROM observations o
WHERE (
    SELECT COUNT(*) FROM observation_photos p
    WHERE p.observation_id = o.id AND p.is_cover = 1
) != 1
"""

_COVER_MISMATCH = """
SELECT COUNT(*) FROM observations o
JOIN observation_photos p
  ON p.observation_id = o.id AND p.is_cover = 1
WHERE o.photo_asset_id IS NOT p.asset_id
"""


def _count(connection, statement: str) -> int:
    return int(connection.execute(text(statement)).scalar() or 0)


def _validate_single_source(connection) -> None:
    problems = {
        "缺少唯一主物种条目": _count(connection, _PRIMARY_MISSING),
        "主物种条目与旧列不一致": _count(connection, _PRIMARY_MISMATCH),
        "缺少唯一封面照片": _count(connection, _COVER_MISSING),
        "封面照片与旧列不一致": _count(connection, _COVER_MISMATCH),
    }
    broken = {name: count for name, count in problems.items() if count}
    if broken:
        detail = "；".join(f"{name} {count} 笔" for name, count in broken.items())
        raise RuntimeError(
            "拒绝单源化迁移：observation_species/observation_photos 与旧列不一致。"
            f" {detail}。请先修复数据并重新备份后再迁移。"
        )


def _ensure_primary_index() -> None:
    inspector = inspect(op.get_bind())
    indexes = {item["name"] for item in inspector.get_indexes("observation_species")}
    if "uq_observation_species_primary" not in indexes:
        op.create_index(
            "uq_observation_species_primary",
            "observation_species",
            ["observation_id"],
            unique=True,
            sqlite_where=sa.text("is_primary = 1"),
        )


def _ensure_cover_index() -> None:
    inspector = inspect(op.get_bind())
    indexes = {item["name"] for item in inspector.get_indexes("observation_photos")}
    if "uq_observation_photos_cover" not in indexes:
        op.create_index(
            "uq_observation_photos_cover",
            "observation_photos",
            ["observation_id"],
            unique=True,
            sqlite_where=sa.text("is_cover = 1"),
        )


def upgrade() -> None:
    connection = op.get_bind()
    inspector = inspect(connection)
    if "observations" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("observations")}
    old_columns = [column for column in _OLD_COLUMNS if column in columns]
    if old_columns and len(old_columns) != len(_OLD_COLUMNS):
        missing = sorted(set(_OLD_COLUMNS) - set(old_columns))
        raise RuntimeError(f"observations 旧列只存在一部分，缺少：{', '.join(missing)}")

    if old_columns:
        _validate_single_source(connection)
        for index in inspector.get_indexes("observations"):
            index_columns = set(index.get("column_names") or [])
            if index_columns & set(_OLD_COLUMNS) and index.get("name"):
                op.drop_index(index["name"], table_name="observations")
        check_names = [
            constraint["name"]
            for constraint in inspector.get_check_constraints("observations")
            if constraint.get("name")
            and "photo_subject_fields" in constraint["name"]
        ]
        if not check_names:
            raise RuntimeError("observations 缺少 photo_subject_fields 约束，无法安全重建")
        with op.batch_alter_table("observations", recreate="always") as batch:
            batch.drop_constraint("photo_subject_fields", type_="check")
            for column in _OLD_COLUMNS:
                batch.drop_column(column)

    _ensure_primary_index()
    _ensure_cover_index()


def downgrade() -> None:
    raise RuntimeError("单源化迁移不能无损降级；请恢复迁移前的完整备份")
