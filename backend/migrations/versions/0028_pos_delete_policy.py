"""describe the implemented safe point-of-sale deletion policy

Revision ID: 0028_pos_delete_policy
Revises: 0027_router_delete_policy
"""
from alembic import op
import sqlalchemy as sa


revision = "0028_pos_delete_policy"
down_revision = "0027_router_delete_policy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.get_bind().execute(
        sa.text(
            "UPDATE permissions SET description = :description "
            "WHERE code = 'pos.delete'"
        ),
        {
            "description": (
                "حذف نقطة بيع متوقفة وغير مرتبطة بكروت أو دفعات أو طباعة "
                "أو حركات مخزون أو قيود مالية أو تخصيصات حسابات الإدارة"
            )
        },
    )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text(
            "UPDATE permissions SET description = :description "
            "WHERE code = 'pos.delete'"
        ),
        {
            "description": "حذف نقاط البيع عند إضافة عملية حذف آمنة"
        },
    )
