"""create granular role permissions

Revision ID: 0018_role_permissions
Revises: 0017_admin_roles
"""
from alembic import op
import sqlalchemy as sa

revision = "0018_role_permissions"
down_revision = "0017_admin_roles"
branch_labels = None
depends_on = None


PERMISSIONS = [
    ("cards.view", "عرض الكروت", "cards", "مشاهدة الكروت وبياناتها"),
    ("cards.manage", "إدارة الكروت", "cards", "إنشاء الكروت وتعديل حالتها"),
    ("sessions.view", "عرض الجلسات", "sessions", "مشاهدة جلسات RADIUS"),
    ("sessions.disconnect", "فصل الجلسات", "sessions", "إنهاء جلسة مستخدم"),
    ("plans.view", "عرض الباقات", "plans", "مشاهدة الباقات"),
    ("plans.manage", "إدارة الباقات", "plans", "إنشاء الباقات وتعديلها"),
    ("routers.view", "عرض الراوترات", "routers", "مشاهدة أجهزة الشبكة"),
    ("routers.manage", "إدارة الراوترات", "routers", "إضافة الراوترات وتعديلها"),
    ("pos.view", "عرض نقاط البيع", "pos", "مشاهدة نقاط البيع والمخزون"),
    ("pos.manage", "إدارة نقاط البيع", "pos", "إدارة نقاط البيع"),
    ("finance.view", "عرض الحسابات المالية", "finance", "مشاهدة الحسابات والتقارير المالية"),
    ("finance.manage", "إدارة الحسابات المالية", "finance", "تسجيل الحركات المالية"),
    ("reports.view", "عرض التقارير", "reports", "مشاهدة التقارير"),
    ("printing.manage", "الطباعة", "printing", "إنشاء عمليات الطباعة وإعادة الطباعة"),
]

MANAGER = [code for code, *_ in PERMISSIONS]
OPERATOR = ["cards.view", "cards.manage", "sessions.view", "sessions.disconnect", "plans.view", "routers.view", "pos.view", "printing.manage", "reports.view"]
VIEWER = ["cards.view", "sessions.view", "plans.view", "routers.view", "pos.view", "finance.view", "reports.view"]


def upgrade() -> None:
    op.create_table(
        "permissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=100), nullable=False, unique=True),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("module", sa.String(length=80), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
    )
    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("permission_id", sa.Integer(), sa.ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
    )
    bind = op.get_bind()
    bind.execute(
        sa.text("INSERT INTO permissions (code, name, module, description) VALUES (:code, :name, :module, :description)"),
        [{"code": code, "name": name, "module": module, "description": description} for code, name, module, description in PERMISSIONS],
    )
    role_rows = bind.execute(sa.text("SELECT id, code FROM roles WHERE code IN ('manager', 'operator', 'viewer')")).mappings().all()
    grants = {"manager": MANAGER, "operator": OPERATOR, "viewer": VIEWER}
    permission_rows = bind.execute(sa.text("SELECT id, code FROM permissions")).mappings().all()
    permission_ids = {row["code"]: row["id"] for row in permission_rows}
    for role in role_rows:
        bind.execute(
            sa.text("INSERT INTO role_permissions (role_id, permission_id) VALUES (:role_id, :permission_id)"),
            [{"role_id": role["id"], "permission_id": permission_ids[code]} for code in grants[role["code"]]],
        )


def downgrade() -> None:
    op.drop_table("role_permissions")
    op.drop_table("permissions")
