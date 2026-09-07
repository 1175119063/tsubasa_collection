"""Allow one observation to contain multiple species-linked photos."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20260905_08"
down_revision = "20260901_07"
branch_labels = None
depends_on = None


def upgrade() -> None:
    tables = set(inspect(op.get_bind()).get_table_names())
    if "observation_photos" not in tables:
        op.create_table(
            "observation_photos",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("observation_id", sa.Integer(), nullable=False),
            sa.Column("asset_id", sa.Integer(), nullable=False),
            sa.Column("observed_at", sa.DateTime(), nullable=False),
            sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_cover", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint("position >= 0", name="observation_photo_position"),
            sa.ForeignKeyConstraint(["observation_id"], ["observations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["asset_id"], ["media_assets.id"], ondelete="RESTRICT"),
            sa.UniqueConstraint("observation_id", "asset_id"),
        )
        op.create_index(
            "ix_observation_photos_observation_id",
            "observation_photos",
            ["observation_id"],
        )
        op.create_index("ix_observation_photos_asset_id", "observation_photos", ["asset_id"])
        op.create_index("ix_observation_photos_is_cover", "observation_photos", ["is_cover"])
        op.execute(
            "INSERT INTO observation_photos "
            "(observation_id, asset_id, observed_at, position, is_cover, created_at, updated_at) "
            "SELECT id, photo_asset_id, observed_at, 0, 1, created_at, updated_at FROM observations"
        )

    tables = set(inspect(op.get_bind()).get_table_names())
    if "observation_photo_species" not in tables:
        op.create_table(
            "observation_photo_species",
            sa.Column("photo_id", sa.Integer(), nullable=False),
            sa.Column("observation_species_id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["photo_id"], ["observation_photos.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["observation_species_id"],
                ["observation_species.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("photo_id", "observation_species_id"),
        )
        op.create_index(
            "ix_observation_photo_species_observation_species_id",
            "observation_photo_species",
            ["observation_species_id"],
        )
        op.execute(
            "INSERT INTO observation_photo_species "
            "(photo_id, observation_species_id, created_at, updated_at) "
            "SELECT p.id, s.id, p.created_at, p.updated_at "
            "FROM observation_photos p JOIN observation_species s "
            "ON s.observation_id = p.observation_id"
        )


def downgrade() -> None:
    op.drop_table("observation_photo_species")
    op.drop_table("observation_photos")
