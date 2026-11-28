"""add auditable point-of-sale finance reversals

Revision ID: 0031_finance_entry_reversals
Revises: 0030_card_delete_policy
"""
from alembic import op
import sqlalchemy as sa


revision = "0031_finance_entry_reversals"
down_revision = "0030_card_delete_policy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pos_account_entries",
        sa.Column("reversal_of_id", sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key(
        "fk_pos_account_entries_reversal_of_id",
        "pos_account_entries",
        "pos_account_entries",
        ["reversal_of_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_unique_constraint(
        "uq_pos_account_entry_reversal",
        "pos_account_entries",
        ["reversal_of_id"],
    )
    op.execute(
        sa.text(
            "UPDATE permissions SET description = :description WHERE code = 'finance.update'"
        ).bindparams(
            description="تعديل البيان والمرجع للحركة المالية دون تغيير المبلغ أو الاتجاه أو نوع القيد"
        )
    )
    op.execute(
        sa.text(
            "UPDATE permissions SET description = :description WHERE code = 'finance.delete'"
        ).bindparams(
            description="عكس الحركة بقيد مقابل مع الاحتفاظ بالقيد الأصلي وسجل التدقيق"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE permissions SET description = :description WHERE code = 'finance.update'"
        ).bindparams(
            description="تعديل حركة مالية إذا أضيفت آلية مراجعة آمنة"
        )
    )
    op.execute(
        sa.text(
            "UPDATE permissions SET description = :description WHERE code = 'finance.delete'"
        ).bindparams(
            description="عكس أو حذف حركة مالية وفق سياسة تدقيق آمنة"
        )
    )
    op.drop_constraint(
        "uq_pos_account_entry_reversal", "pos_account_entries", type_="unique"
    )
    op.drop_constraint(
        "fk_pos_account_entries_reversal_of_id", "pos_account_entries", type_="foreignkey"
    )
    op.drop_column("pos_account_entries", "reversal_of_id")
