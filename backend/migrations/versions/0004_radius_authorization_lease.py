"""add short-lived RADIUS authorization reservation

Revision ID: 0004_radius_authorization_lease
Revises: 0003_print_job_items
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_radius_authorization_lease"
down_revision = "0003_print_job_items"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cards",
        sa.Column("radius_auth_reserved_until", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_cards_radius_auth_reserved_until",
        "cards",
        ["radius_auth_reserved_until"],
    )


def downgrade() -> None:
    op.drop_index("ix_cards_radius_auth_reserved_until", table_name="cards")
    op.drop_column("cards", "radius_auth_reserved_until")
