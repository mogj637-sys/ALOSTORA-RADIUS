"""add staged User Manager import preview rows

Revision ID: 0010_user_manager_preview
Revises: 0009_user_manager_sync
"""
from alembic import op
import sqlalchemy as sa

revision = "0010_user_manager_preview"
down_revision = "0009_user_manager_sync"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_manager_import_previews",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "sync_run_id", sa.Uuid(),
            sa.ForeignKey("user_manager_sync_runs.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("external_user_id", sa.String(160), nullable=False),
        sa.Column("username", sa.String(120), nullable=False),
        sa.Column("source_profile_id", sa.String(160), nullable=True),
        sa.Column("classification", sa.String(30), nullable=False),
        sa.Column(
            "matched_card_id", sa.Uuid(),
            sa.ForeignKey("cards.id", ondelete="RESTRICT"), nullable=True,
        ),
        sa.Column("safe_snapshot", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("issues", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("source_fingerprint", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "sync_run_id", "external_user_id",
            name="uq_um_import_preview_run_external_user",
        ),
    )
    op.create_index(
        "ix_um_import_preview_run_classification",
        "user_manager_import_previews", ["sync_run_id", "classification"],
    )
    op.create_index(
        "ix_um_import_preview_username",
        "user_manager_import_previews", ["username"],
    )


def downgrade() -> None:
    op.drop_index("ix_um_import_preview_username", table_name="user_manager_import_previews")
    op.drop_index("ix_um_import_preview_run_classification", table_name="user_manager_import_previews")
    op.drop_table("user_manager_import_previews")
