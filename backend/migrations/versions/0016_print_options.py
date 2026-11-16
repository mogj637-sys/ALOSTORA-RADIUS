"""persist print layout selections

Revision ID: 0016_print_options
Revises: 0015_card_batches
"""
from alembic import op
import sqlalchemy as sa

revision = "0016_print_options"
down_revision = "0015_card_batches"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "print_jobs",
        sa.Column("print_options", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )


def downgrade() -> None:
    op.drop_column("print_jobs", "print_options")
