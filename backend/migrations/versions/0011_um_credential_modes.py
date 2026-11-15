"""store per-card User Manager credential metadata

Revision ID: 0011_um_credential_modes
Revises: 0010_user_manager_preview
"""
from alembic import op
import sqlalchemy as sa

revision = "0011_um_credential_modes"
down_revision = "0010_user_manager_preview"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_manager_import_previews",
        sa.Column("credential_mode", sa.String(length=30), nullable=True),
    )
    op.add_column(
        "user_manager_import_previews",
        sa.Column(
            "credential_state",
            sa.String(length=30),
            nullable=False,
            server_default="unavailable",
        ),
    )
    op.add_column(
        "user_manager_card_sources",
        sa.Column("credential_mode", sa.String(length=30), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_manager_card_sources", "credential_mode")
    op.drop_column("user_manager_import_previews", "credential_state")
    op.drop_column("user_manager_import_previews", "credential_mode")
