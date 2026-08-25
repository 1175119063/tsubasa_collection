"""Allow one trip to contain multiple ordered locations."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20260819_03"
down_revision = "20260818_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    if "trip_locations" not in inspect(connection).get_table_names():
        op.create_table(
            "trip_locations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("trip_id", sa.Integer(), nullable=False),
            sa.Column("location_id", sa.Integer(), nullable=False),
            sa.Column("visit_order", sa.Integer(), nullable=False),
            sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["trip_id"], ["birding_trips.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["location_id"], ["birding_locations.id"], ondelete="RESTRICT"),
            sa.UniqueConstraint("trip_id", "location_id"),
        )
        for column in ("trip_id", "location_id", "is_primary"):
            op.create_index(f"ix_trip_locations_{column}", "trip_locations", [column])
    tables = inspect(connection).get_table_names()
    if "birding_locations" in tables:
        op.execute(
            "INSERT INTO trip_locations "
            "(trip_id, location_id, visit_order, is_primary, created_at, updated_at) "
            "SELECT id, location_id, 1, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP "
            "FROM birding_trips WHERE EXISTS "
            "(SELECT 1 FROM birding_locations WHERE id = birding_trips.location_id) "
            "AND NOT EXISTS "
            "(SELECT 1 FROM trip_locations WHERE trip_id = birding_trips.id)"
        )


def downgrade() -> None:
    op.drop_table("trip_locations")
