"""add online sale flag and notes to card batches

Revision ID: 0023_card_batch_metadata
Revises: 0022_user_access_overrides
"""
from alembic import op
import sqlalchemy as sa

revision = "0023_card_batch_metadata"
down_revision = "0022_user_access_overrides"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "card_batches",
        sa.Column("is_online_sale", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "card_batches",
        sa.Column("note", sa.Text(), nullable=True),
    )
    op.alter_column("card_batches", "is_online_sale", server_default=None)


def downgrade() -> None:
    op.drop_column("card_batches", "note")
    op.drop_column("card_batches", "is_online_sale")
