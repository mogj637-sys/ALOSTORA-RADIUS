"""describe the implemented safe router deletion policy

Revision ID: 0027_router_delete_policy
Revises: 0026_plan_delete_policy
"""
from alembic import op
import sqlalchemy as sa


revision = "0027_router_delete_policy"
down_revision = "0026_plan_delete_policy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.get_bind().execute(
        sa.text(
            "UPDATE permissions SET description = :description "
            "WHERE code = 'routers.delete'"
        ),
        {
            "description": (
                "حذف راوتر متوقف وغير مرتبط بجلسات RADIUS أو سجلات User Manager"
            )
        },
    )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text(
            "UPDATE permissions SET description = :description "
            "WHERE code = 'routers.delete'"
        ),
        {
            "description": "حذف الراوترات عند إضافة عملية حذف آمنة"
        },
    )
