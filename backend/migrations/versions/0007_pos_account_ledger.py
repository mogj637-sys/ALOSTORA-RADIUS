"""add append-only point of sale account ledger

Revision ID: 0007_pos_account_ledger
Revises: 0006_router_nas_addr
"""
from alembic import op
import sqlalchemy as sa

revision = "0007_pos_account_ledger"
down_revision = "0006_router_nas_addr"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pos_account_entries",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("point_of_sale_id", sa.Integer(), sa.ForeignKey("points_of_sale.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("entry_type", sa.String(30), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("reference", sa.String(120), nullable=True),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("created_by", sa.String(120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_pos_account_entry_amount_positive"),
        sa.UniqueConstraint("idempotency_key", name="uq_pos_account_entry_idempotency"),
    )
    op.create_index("ix_pos_account_entries_pos_created", "pos_account_entries", ["point_of_sale_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_pos_account_entries_pos_created", table_name="pos_account_entries")
    op.drop_table("pos_account_entries")
