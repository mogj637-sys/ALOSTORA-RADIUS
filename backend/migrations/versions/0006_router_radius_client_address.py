"""add explicit RADIUS client source address to routers

Revision ID: 0006_router_radius_client_address
Revises: 0005_radius_session_card_state
"""
from alembic import op
import sqlalchemy as sa

revision = "0006_router_radius_client_address"
down_revision = "0005_radius_session_card_state"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "routers",
        sa.Column("radius_client_address", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("routers", "radius_client_address")
