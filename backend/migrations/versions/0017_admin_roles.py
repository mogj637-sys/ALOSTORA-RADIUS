"""seed built-in administrator roles

Revision ID: 0017_admin_roles
Revises: 0016_print_options
"""
from alembic import op
import sqlalchemy as sa

revision = "0017_admin_roles"
down_revision = "0016_print_options"
branch_labels = None
depends_on = None


def upgrade() -> None:
    roles = sa.table(
        "roles",
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
    )
    op.bulk_insert(
        roles,
        [
            {"code": "manager", "name": "مدير تشغيل", "description": "إدارة التشغيل اليومي ومتابعة المستخدمين والكروت"},
            {"code": "operator", "name": "موظف تشغيل", "description": "تنفيذ مهام التشغيل المسموح بها"},
            {"code": "viewer", "name": "مشاهد", "description": "عرض البيانات والتقارير دون تعديل"},
        ],
    )


def downgrade() -> None:
    op.execute("DELETE FROM roles WHERE code IN ('manager', 'operator', 'viewer')")
