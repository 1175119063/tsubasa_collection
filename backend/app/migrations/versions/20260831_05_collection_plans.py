"""Add user-defined collection plans and evidence slots."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20260831_05"
down_revision = "20260822_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "collection_plans" in inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "collection_plans",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("introduction", sa.Text(), nullable=True),
        sa.Column("template_kind", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "collection_plan_subitems",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=80), nullable=False),
        sa.Column("label_key", sa.String(length=80), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], ["collection_plans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_id", "label_key"),
        sa.UniqueConstraint("plan_id", "position"),
    )
    op.create_index(
        "ix_collection_plan_subitems_plan_id",
        "collection_plan_subitems",
        ["plan_id"],
    )
    op.create_table(
        "collection_plan_species",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("species_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], ["collection_plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["species_id"], ["species.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_id", "position"),
        sa.UniqueConstraint("plan_id", "species_id"),
    )
    op.create_index(
        "ix_collection_plan_species_plan_id", "collection_plan_species", ["plan_id"]
    )
    op.create_index(
        "ix_collection_plan_species_species_id", "collection_plan_species", ["species_id"]
    )
    op.create_table(
        "collection_plan_slots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("membership_id", sa.Integer(), nullable=False),
        sa.Column("subitem_id", sa.Integer(), nullable=False),
        sa.Column("observation_species_id", sa.Integer(), nullable=True),
        sa.Column("crop_center_x", sa.Float(), nullable=False),
        sa.Column("crop_center_y", sa.Float(), nullable=False),
        sa.Column("crop_zoom", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "crop_center_x >= 0 AND crop_center_x <= 1",
            name="ck_collection_plan_slots_crop_center_x_range",
        ),
        sa.CheckConstraint(
            "crop_center_y >= 0 AND crop_center_y <= 1",
            name="ck_collection_plan_slots_crop_center_y_range",
        ),
        sa.CheckConstraint(
            "crop_zoom >= 1 AND crop_zoom <= 4",
            name="ck_collection_plan_slots_crop_zoom_range",
        ),
        sa.ForeignKeyConstraint(
            ["membership_id"], ["collection_plan_species.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["observation_species_id"], ["observation_species.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["subitem_id"], ["collection_plan_subitems.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("membership_id", "subitem_id"),
    )
    op.create_index(
        "ix_collection_plan_slots_membership_id",
        "collection_plan_slots",
        ["membership_id"],
    )
    op.create_index(
        "ix_collection_plan_slots_observation_species_id",
        "collection_plan_slots",
        ["observation_species_id"],
    )
    op.create_index(
        "ix_collection_plan_slots_subitem_id", "collection_plan_slots", ["subitem_id"]
    )


def downgrade() -> None:
    op.drop_table("collection_plan_slots")
    op.drop_table("collection_plan_species")
    op.drop_table("collection_plan_subitems")
    op.drop_table("collection_plans")
