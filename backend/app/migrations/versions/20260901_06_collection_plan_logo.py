"""Add a user-selected logo to collection plans."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20260901_06"
down_revision = "20260831_05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {
        column["name"]
        for column in inspect(op.get_bind()).get_columns("collection_plans")
    }
    if "logo_asset_id" in columns:
        return
    with op.batch_alter_table("collection_plans") as batch_op:
        batch_op.add_column(sa.Column("logo_asset_id", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("logo_observation_species_id", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "logo_crop_center_x",
                sa.Float(),
                nullable=False,
                server_default="0.5",
            )
        )
        batch_op.add_column(
            sa.Column(
                "logo_crop_center_y",
                sa.Float(),
                nullable=False,
                server_default="0.5",
            )
        )
        batch_op.add_column(
            sa.Column(
                "logo_crop_zoom", sa.Float(), nullable=False, server_default="1.0"
            )
        )
        batch_op.create_foreign_key(
            "fk_collection_plans_logo_asset_id_media_assets",
            "media_assets",
            ["logo_asset_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_foreign_key(
            "fk_collection_plans_logo_observation_species_id_observation_species",
            "observation_species",
            ["logo_observation_species_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_check_constraint(
            "ck_collection_plans_logo_single_source",
            "NOT (logo_asset_id IS NOT NULL AND logo_observation_species_id IS NOT NULL)",
        )
        batch_op.create_check_constraint(
            "ck_collection_plans_logo_crop_center_x_range",
            "logo_crop_center_x >= 0 AND logo_crop_center_x <= 1",
        )
        batch_op.create_check_constraint(
            "ck_collection_plans_logo_crop_center_y_range",
            "logo_crop_center_y >= 0 AND logo_crop_center_y <= 1",
        )
        batch_op.create_check_constraint(
            "ck_collection_plans_logo_crop_zoom_range",
            "logo_crop_zoom >= 1 AND logo_crop_zoom <= 4",
        )
    op.create_index(
        "ix_collection_plans_logo_asset_id", "collection_plans", ["logo_asset_id"]
    )
    op.create_index(
        "ix_collection_plans_logo_observation_species_id",
        "collection_plans",
        ["logo_observation_species_id"],
    )


def downgrade() -> None:
    with op.batch_alter_table("collection_plans") as batch_op:
        batch_op.drop_column("logo_crop_zoom")
        batch_op.drop_column("logo_crop_center_y")
        batch_op.drop_column("logo_crop_center_x")
        batch_op.drop_column("logo_observation_species_id")
        batch_op.drop_column("logo_asset_id")
