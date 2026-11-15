"""add plan commission settings

Revision ID: 0008_plan_commission
Revises: 0007_pos_account_ledger
"""
from alembic import op
import sqlalchemy as sa

revision = "0008_plan_commission"
down_revision = "0007_pos_account_ledger"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "plans",
        sa.Column("commission_type", sa.String(20), nullable=False, server_default="none"),
    )
    op.add_column(
        "plans",
        sa.Column("commission_value", sa.Numeric(12, 2), nullable=False, server_default="0"),
    )
    op.create_check_constraint(
        "ck_plans_commission_nonnegative", "plans", "commission_value >= 0"
    )
    op.create_check_constraint(
        "ck_plans_commission_percentage_max",
        "plans",
        "commission_type != 'percentage' OR commission_value <= 100",
    )
    op.create_check_constraint(
        "ck_plans_fixed_commission_not_above_price",
        "plans",
        "commission_type != 'fixed' OR commission_value <= price",
    )


def downgrade() -> None:
    op.drop_constraint("ck_plans_fixed_commission_not_above_price", "plans", type_="check")
    op.drop_constraint("ck_plans_commission_percentage_max", "plans", type_="check")
    op.drop_constraint("ck_plans_commission_nonnegative", "plans", type_="check")
    op.drop_column("plans", "commission_value")
    op.drop_column("plans", "commission_type")
