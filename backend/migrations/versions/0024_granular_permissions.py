"""add granular section and operation permissions

Revision ID: 0024_granular_permissions
Revises: 0023_card_batch_metadata
"""
from alembic import op
import sqlalchemy as sa

revision = "0024_granular_permissions"
down_revision = "0023_card_batch_metadata"
branch_labels = None
depends_on = None


PERMISSIONS = [
    ("cards.create", "إنشاء الكروت", "cards", "إنشاء كرت منفرد أو دفعة كروت"),
    ("cards.credentials", "عرض بيانات دخول الكروت", "cards", "إظهار كلمات مرور الكروت الناتجة عند الإنشاء"),
    ("cards.update", "تعديل الكروت", "cards", "تغيير حالة الكرت وبياناته المسموح بها"),
    ("cards.delete", "حذف الكروت", "cards", "حذف الكروت عند إضافة عملية حذف آمنة"),
    ("plans.create", "إضافة الباقات", "plans", "إنشاء باقة جديدة"),
    ("plans.update", "تعديل الباقات", "plans", "تعديل إعدادات الباقات"),
    ("plans.delete", "حذف الباقات", "plans", "حذف الباقات عند إضافة عملية حذف آمنة"),
    ("templates.view", "عرض تصاميم الكروت", "templates", "عرض القوالب ومعاينتها"),
    ("templates.create", "إنشاء تصاميم الكروت", "templates", "إنشاء قالب طباعة"),
    ("templates.update", "تعديل تصاميم الكروت", "templates", "تعديل القوالب وربطها بالباقة"),
    ("templates.delete", "حذف تصاميم الكروت", "templates", "حذف قالب غير مستخدم"),
    ("routers.create", "إضافة الراوترات", "routers", "تسجيل راوتر جديد"),
    ("routers.update", "تعديل الراوترات", "routers", "تعديل إعدادات الراوتر وتفعيله أو إيقافه"),
    ("routers.delete", "حذف الراوترات", "routers", "حذف الراوترات عند إضافة عملية حذف آمنة"),
    ("pos.create", "إضافة نقاط البيع", "pos", "إنشاء نقطة بيع"),
    ("pos.update", "تعديل نقاط البيع", "pos", "تعديل بيانات نقطة البيع وإعداداتها المسموحة"),
    ("pos.delete", "حذف نقاط البيع", "pos", "حذف نقاط البيع عند إضافة عملية حذف آمنة"),
    ("finance.create", "تسجيل الحركات المالية", "finance", "إضافة حركة مالية إلى حساب نقطة البيع"),
    ("finance.update", "تعديل الحركات المالية", "finance", "تعديل حركة مالية إذا أضيفت آلية مراجعة آمنة"),
    ("finance.delete", "حذف الحركات المالية", "finance", "عكس أو حذف حركة مالية وفق سياسة تدقيق آمنة"),
    ("printing.view", "عرض سجل الطباعة", "printing", "مشاهدة عمليات الطباعة دون كلمات المرور"),
    ("printing.create", "تنفيذ الطباعة", "printing", "إنشاء عملية طباعة للكروت"),
    ("printing.reprint", "إعادة الطباعة", "printing", "إعادة طباعة عملية سابقة"),
    ("printing.credentials", "عرض بيانات دخول الكروت للطباعة", "printing", "صلاحية حساسة مستقلة لإظهار كلمات مرور الكروت"),
    ("audit.view", "عرض سجل العمليات", "audit", "مشاهدة سجل التدقيق الإداري"),
]


MANAGER = [code for code, *_ in PERMISSIONS]
OPERATOR = [
    "cards.create",
    "cards.update",
    "templates.view",
    "printing.view",
]
VIEWER = [
    "templates.view",
    "printing.view",
]


def upgrade() -> None:
    bind = op.get_bind()
    op.bulk_insert(
        sa.table(
            "permissions",
            sa.column("code", sa.String),
            sa.column("name", sa.String),
            sa.column("module", sa.String),
            sa.column("description", sa.Text),
        ),
        [
            {"code": code, "name": name, "module": module, "description": description}
            for code, name, module, description in PERMISSIONS
        ],
    )

    permission_rows = bind.execute(
        sa.text("SELECT id, code FROM permissions")
    ).mappings().all()
    permission_ids = {row["code"]: row["id"] for row in permission_rows}
    role_rows = bind.execute(
        sa.text("SELECT id, code FROM roles WHERE code IN ('manager', 'operator', 'viewer')")
    ).mappings().all()
    grants = {"manager": MANAGER, "operator": OPERATOR, "viewer": VIEWER}

    for role in role_rows:
        bind.execute(
            sa.text(
                "INSERT INTO role_permissions (role_id, permission_id) "
                "VALUES (:role_id, :permission_id)"
            ),
            [
                {"role_id": role["id"], "permission_id": permission_ids[code]}
                for code in grants[role["code"]]
            ],
        )

    # Replace the operator's former broad grants with the narrower action grants above.
    bind.execute(
        sa.text(
            "DELETE FROM role_permissions "
            "WHERE role_id = (SELECT id FROM roles WHERE code = 'operator') "
            "AND permission_id IN ("
            "SELECT id FROM permissions WHERE code IN ('cards.manage', 'printing.manage')"
            ")"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    codes = [code for code, *_ in PERMISSIONS]
    bind.execute(
        sa.text(
            "DELETE FROM admin_user_permission_overrides "
            "WHERE permission_id IN (SELECT id FROM permissions WHERE code IN :codes)"
        ).bindparams(sa.bindparam("codes", expanding=True)),
        {"codes": codes},
    )
    bind.execute(
        sa.text(
            "DELETE FROM role_permissions "
            "WHERE permission_id IN (SELECT id FROM permissions WHERE code IN :codes)"
        ).bindparams(sa.bindparam("codes", expanding=True)),
        {"codes": codes},
    )
    bind.execute(
        sa.text("DELETE FROM permissions WHERE code IN :codes").bindparams(
            sa.bindparam("codes", expanding=True)
        ),
        {"codes": codes},
    )
    # Restore the operator's legacy broad permissions when downgrading.
    operator = bind.execute(
        sa.text("SELECT id FROM roles WHERE code = 'operator'")
    ).scalar_one_or_none()
    permission_rows = bind.execute(
        sa.text("SELECT id FROM permissions WHERE code IN ('cards.manage', 'printing.manage')")
    ).mappings().all()
    if operator is not None:
        bind.execute(
            sa.text(
                "INSERT INTO role_permissions (role_id, permission_id) "
                "VALUES (:role_id, :permission_id) ON CONFLICT DO NOTHING"
            ),
            [
                {"role_id": operator, "permission_id": row["id"]}
                for row in permission_rows
            ],
        )
