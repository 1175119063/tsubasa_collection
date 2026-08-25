"""Establish the versioned schema baseline."""

from alembic import op
from app import models  # noqa: F401
from app.database import Base
from sqlalchemy import inspect, text

revision = "20260818_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    Base.metadata.create_all(connection)
    inspector = inspect(connection)
    if "birding_trips" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("birding_trips")}
        if "name" not in columns:
            connection.execute(text("ALTER TABLE birding_trips ADD COLUMN name VARCHAR(180)"))


def downgrade() -> None:
    # The baseline never destroys a user's personal archive.
    pass
