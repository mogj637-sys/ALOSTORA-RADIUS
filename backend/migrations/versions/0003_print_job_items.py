"""add immutable print job item records

Revision ID: 0003_print_job_items
Revises: 0002_admin_auth
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_print_job_items"
down_revision = "0002_admin_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "print_job_items",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "print_job_id",
            sa.Uuid(),
            sa.ForeignKey("print_jobs.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "card_id",
            sa.Uuid(),
            sa.ForeignKey("cards.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("serial_number_snapshot", sa.String(80), nullable=False),
        sa.Column("username_snapshot", sa.String(120), nullable=False),
        sa.Column("is_free", sa.Boolean(), nullable=False),
        sa.Column("price_snapshot", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("print_job_id", "card_id", name="uq_print_job_item_card"),
    )
    op.create_index("ix_print_job_items_card", "print_job_items", ["card_id"])


def downgrade() -> None:
    op.drop_index("ix_print_job_items_card", table_name="print_job_items")
    op.drop_table("print_job_items")
