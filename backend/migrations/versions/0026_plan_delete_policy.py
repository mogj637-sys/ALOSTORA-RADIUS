"""describe the implemented safe plan deletion policy

Revision ID: 0026_plan_delete_policy
Revises: 0025_credential_access_opt_in
"""
from alembic import op
import sqlalchemy as sa


revision = "0026_plan_delete_policy"
down_revision = "0025_credential_access_opt_in"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.get_bind().execute(
        sa.text(
            "UPDATE permissions SET description = :description "
            "WHERE code = 'plans.delete'"
        ),
        {
            "description": (
                "حذف باقة متوقفة وغير مرتبطة بكروت أو دفعات أو قوالب محفوظة"
            )
        },
    )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text(
            "UPDATE permissions SET description = :description "
            "WHERE code = 'plans.delete'"
        ),
        {
            "description": "حذف الباقات عند إضافة عملية حذف آمنة"
        },
    )
