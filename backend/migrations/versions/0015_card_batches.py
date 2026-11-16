"""persist generated card batches

Revision ID: 0015_card_batches
Revises: 0014_template_plan
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0015_card_batches"
down_revision = "0014_template_plan"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "card_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("batch_number", sa.String(length=40), nullable=False, unique=True),
        sa.Column("plan_id", sa.Integer(), sa.ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("point_of_sale_id", sa.Integer(), sa.ForeignKey("points_of_sale.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("template_code", sa.String(length=80), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("card_type", sa.String(length=30), nullable=False),
        sa.Column("generation_mode", sa.String(length=30), nullable=False, server_default="digits"),
        sa.Column("username_length", sa.Integer(), nullable=False, server_default="8"),
        sa.Column("password_length", sa.Integer(), nullable=False, server_default="8"),
        sa.Column("prefix", sa.String(length=20), nullable=False, server_default=""),
        sa.Column("requested_by", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_card_batches_quantity_positive"),
    )
    op.create_index("ix_card_batches_created_at", "card_batches", ["created_at"])
    op.create_index("ix_card_batches_pos_created", "card_batches", ["point_of_sale_id", "created_at"])
    op.add_column("cards", sa.Column("batch_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_cards_batch_id_card_batches",
        "cards",
        "card_batches",
        ["batch_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_cards_batch_id", "cards", ["batch_id"])


def downgrade() -> None:
    op.drop_index("ix_cards_batch_id", table_name="cards")
    op.drop_constraint("fk_cards_batch_id_card_batches", "cards", type_="foreignkey")
    op.drop_column("cards", "batch_id")
    op.drop_index("ix_card_batches_pos_created", table_name="card_batches")
    op.drop_index("ix_card_batches_created_at", table_name="card_batches")
    op.drop_table("card_batches")
