"""Add species entries so one observation can contain multiple species."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20260818_02"
down_revision = "20260818_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    if "observation_species" not in inspect(connection).get_table_names():
        op.create_table(
            "observation_species",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("observation_id", sa.Integer(), nullable=False),
            sa.Column("species_id", sa.Integer(), nullable=False),
            sa.Column("subspecies_id", sa.Integer(), nullable=True),
            sa.Column("photo_type", sa.String(length=10), nullable=False),
            sa.Column("sex", sa.String(length=10), nullable=True),
            sa.Column("life_stage", sa.String(length=10), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["observation_id"], ["observations.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(["species_id"], ["species.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["subspecies_id"], ["subspecies.id"], ondelete="RESTRICT"
            ),
            sa.UniqueConstraint("observation_id", "species_id"),
            sa.CheckConstraint(
                "(photo_type = 'group' AND sex IS NULL AND life_stage IS NULL "
                "AND subspecies_id IS NULL) OR "
                "(photo_type = 'individual' AND sex IS NOT NULL "
                "AND life_stage IS NOT NULL)",
                name="ck_observation_species_subject_fields",
            ),
        )
        for column in ("observation_id", "species_id", "subspecies_id", "is_primary"):
            op.create_index(
                f"ix_observation_species_{column}", "observation_species", [column]
            )
    op.execute(
        "INSERT INTO observation_species "
        "(observation_id, species_id, subspecies_id, photo_type, sex, life_stage, notes, "
        "is_primary, created_at, updated_at) "
        "SELECT id, species_id, subspecies_id, photo_type, sex, life_stage, NULL, 1, "
        "created_at, updated_at FROM observations "
        "WHERE NOT EXISTS (SELECT 1 FROM observation_species)"
    )


def downgrade() -> None:
    op.drop_table("observation_species")
