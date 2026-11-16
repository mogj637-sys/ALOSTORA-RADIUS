"""add point-of-sale credit limits and operation controls

Revision ID: 0021_pos_credit_limits
Revises: 0020_admin_user_pos_scope
"""
from alembic import op
import sqlalchemy as sa

revision = "0021_pos_credit_limits"
down_revision = "0020_admin_user_pos_scope"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "points_of_sale",
        sa.Column("debt_limit", sa.Numeric(12, 2), nullable=True),
    )
    op.add_column(
        "points_of_sale",
        sa.Column("allow_card_creation", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "points_of_sale",
        sa.Column("allow_printing", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_check_constraint(
        "ck_points_of_sale_debt_limit_nonnegative",
        "points_of_sale",
        "debt_limit IS NULL OR debt_limit >= 0",
    )
    op.alter_column("points_of_sale", "allow_card_creation", server_default=None)
    op.alter_column("points_of_sale", "allow_printing", server_default=None)


def downgrade() -> None:
    op.drop_constraint(
        "ck_points_of_sale_debt_limit_nonnegative",
        "points_of_sale",
        type_="check",
    )
    op.drop_column("points_of_sale", "allow_printing")
    op.drop_column("points_of_sale", "allow_card_creation")
    op.drop_column("points_of_sale", "debt_limit")
