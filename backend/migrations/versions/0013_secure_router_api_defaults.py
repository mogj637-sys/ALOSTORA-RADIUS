"""make secure RouterOS API transport the default for new routers

Revision ID: 0013_secure_router_api_defaults
Revises: 0012_router_api_tls
"""
from alembic import op
import sqlalchemy as sa

revision = "0013_secure_router_api_defaults"
down_revision = "0012_router_api_tls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Preserve existing router settings; only change defaults for future rows.
    op.alter_column(
        "routers",
        "api_port",
        existing_type=sa.Integer(),
        existing_nullable=False,
        server_default=sa.text("8729"),
    )
    op.alter_column(
        "routers",
        "api_use_ssl",
        existing_type=sa.Boolean(),
        existing_nullable=False,
        server_default=sa.true(),
    )


def downgrade() -> None:
    op.alter_column(
        "routers",
        "api_use_ssl",
        existing_type=sa.Boolean(),
        existing_nullable=False,
        server_default=sa.false(),
    )
    op.alter_column(
        "routers",
        "api_port",
        existing_type=sa.Integer(),
        existing_nullable=False,
        server_default=None,
    )
