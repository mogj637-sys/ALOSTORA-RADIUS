"""remember card state before a RADIUS session

Revision ID: 0005_radius_session_card_state
Revises: 0004_radius_authorization_lease
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_radius_session_card_state"
down_revision = "0004_radius_authorization_lease"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "radius_sessions",
        sa.Column("card_status_before_session", sa.String(30), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("radius_sessions", "card_status_before_session")
