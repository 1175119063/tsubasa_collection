"""Associate behavior tags with any number of observation species entries."""

import sqlalchemy as sa
from alembic import op

revision = "20261022_09"
down_revision = "20260905_08"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "observation_behaviors" not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table(
            "observation_behaviors",
            sa.Column("tag_id", sa.Integer(), nullable=False),
            sa.Column("observation_species_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["tag_id"], ["species_behavior_tags.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["observation_species_id"], ["observation_species.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("tag_id", "observation_species_id"),
        )
        op.create_index(
            "ix_observation_behaviors_observation_species_id",
            "observation_behaviors", ["observation_species_id"],
        )
    op.execute(
        "INSERT OR IGNORE INTO observation_behaviors (tag_id, observation_species_id) "
        "SELECT t.id, e.id FROM species_behavior_tags t JOIN observation_species e "
        "ON e.observation_id = t.observation_id AND e.species_id = t.species_id"
    )
    # Keep the nullable legacy column for schema compatibility, not as a second source of truth.
    op.execute("UPDATE species_behavior_tags SET observation_id = NULL")


def downgrade() -> None:
    raise RuntimeError("多观察行为关联不能无损降级；请恢复升级前的完整备份")
