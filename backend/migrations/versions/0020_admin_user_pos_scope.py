"""assign admin users to one or more points of sale

Revision ID: 0020_admin_user_pos_scope
Revises: 0019_audit_logs
"""
from alembic import op
import sqlalchemy as sa

revision = "0020_admin_user_pos_scope"
down_revision = "0019_audit_logs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_user_points_of_sale",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("admin_users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("point_of_sale_id", sa.Integer(), sa.ForeignKey("points_of_sale.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_index(
        "ix_admin_user_points_of_sale_point",
        "admin_user_points_of_sale",
        ["point_of_sale_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_admin_user_points_of_sale_point", table_name="admin_user_points_of_sale")
    op.drop_table("admin_user_points_of_sale")
