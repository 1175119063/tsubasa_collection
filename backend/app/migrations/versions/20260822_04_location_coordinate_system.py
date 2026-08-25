"""Track the coordinate system used by location center points."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20260822_04"
down_revision = "20260819_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    columns = {column["name"] for column in inspect(connection).get_columns("birding_locations")}
    if "coordinate_system" not in columns:
        op.add_column(
            "birding_locations",
            sa.Column(
                "coordinate_system",
                sa.String(length=12),
                nullable=False,
                server_default="wgs84",
            ),
        )


def downgrade() -> None:
    connection = op.get_bind()
    columns = {column["name"] for column in inspect(connection).get_columns("birding_locations")}
    if "coordinate_system" in columns:
        op.drop_column("birding_locations", "coordinate_system")
