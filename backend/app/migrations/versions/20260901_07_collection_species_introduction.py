"""Add plan-specific introductions to collection species."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20260901_07"
down_revision = "20260901_06"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {
        column["name"]
        for column in inspect(op.get_bind()).get_columns("collection_plan_species")
    }
    if "introduction" in columns:
        return
    with op.batch_alter_table("collection_plan_species") as batch_op:
        batch_op.add_column(sa.Column("introduction", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("collection_plan_species") as batch_op:
        batch_op.drop_column("introduction")
