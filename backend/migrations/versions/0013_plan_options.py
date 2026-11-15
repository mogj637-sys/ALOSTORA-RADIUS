"""add extensible package options

Revision ID: 0013_plan_options
Revises: 0012_card_templates
"""
from alembic import op
import sqlalchemy as sa

revision = "0013_plan_options"
down_revision = "0012_card_templates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "plans",
        sa.Column("settings", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )


def downgrade() -> None:
    op.drop_column("plans", "settings")
