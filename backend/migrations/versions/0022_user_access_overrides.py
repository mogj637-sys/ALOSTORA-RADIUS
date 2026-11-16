"""add per-user permission overrides and card visibility

Revision ID: 0022_user_access_overrides
Revises: 0021_pos_credit_limits
"""
from alembic import op
import sqlalchemy as sa

revision = "0022_user_access_overrides"
down_revision = "0021_pos_credit_limits"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "admin_users",
        sa.Column("card_visibility", sa.String(length=20), nullable=True),
    )
    op.execute(
        """
        UPDATE admin_users
        SET card_visibility = CASE
            WHEN EXISTS (
                SELECT 1 FROM admin_user_points_of_sale scope
                WHERE scope.user_id = admin_users.id
            ) THEN 'assigned'
            ELSE 'search_any'
        END
        """
    )
    op.alter_column(
        "admin_users",
        "card_visibility",
        existing_type=sa.String(length=20),
        nullable=False,
        server_default="search_any",
    )
    op.create_check_constraint(
        "ck_admin_users_card_visibility",
        "admin_users",
        "card_visibility IN ('all', 'assigned', 'search_any')",
    )
    op.create_table(
        "admin_user_permission_overrides",
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("admin_users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "permission_id",
            sa.Integer(),
            sa.ForeignKey("permissions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("allowed", sa.Boolean(), nullable=False),
    )
    op.create_index(
        "ix_admin_user_permission_overrides_permission",
        "admin_user_permission_overrides",
        ["permission_id"],
    )
    op.alter_column(
        "admin_users",
        "card_visibility",
        existing_type=sa.String(length=20),
        server_default=None,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_admin_user_permission_overrides_permission",
        table_name="admin_user_permission_overrides",
    )
    op.drop_table("admin_user_permission_overrides")
    op.drop_constraint(
        "ck_admin_users_card_visibility",
        "admin_users",
        type_="check",
    )
    op.drop_column("admin_users", "card_visibility")
