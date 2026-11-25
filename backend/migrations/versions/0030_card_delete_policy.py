"""describe the safe logical card deletion operation

Revision ID: 0030_card_delete_policy
Revises: 0029_radius_session_idx
"""
from alembic import op
import sqlalchemy as sa


revision = "0030_card_delete_policy"
down_revision = "0029_radius_session_idx"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE permissions SET description = :description WHERE code = 'cards.delete'"
        ).bindparams(
            description="إلغاء منطقي لكرت غير مستخدم وغير مخصص مع الاحتفاظ بسجل التدقيق والطباعة"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE permissions SET description = :description WHERE code = 'cards.delete'"
        ).bindparams(
            description="حذف الكروت عند إضافة عملية حذف آمنة"
        )
    )
