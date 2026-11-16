"""complete the granular administrative permission catalog

Revision ID: 0020_granular_admin_permissions
Revises: 0019_audit_logs
"""
from alembic import op
import sqlalchemy as sa

revision = "0020_granular_admin_permissions"
down_revision = "0019_audit_logs"
branch_labels = None
depends_on = None


NEW_PERMISSIONS = [
    ("cards.create", "إضافة الكروت", "cards", "إنشاء كرت منفرد أو دفعة كروت"),
    ("cards.update", "تعديل الكروت", "cards", "تغيير حالة الكرت وإجراءاته المسموحة"),
    ("cards.credentials", "عرض بيانات دخول الكروت", "cards", "استلام اسم المستخدم وكلمة المرور عند إنشاء الكروت"),
    ("plans.create", "إضافة الباقات", "plans", "إنشاء باقة جديدة"),
    ("plans.update", "تعديل الباقات", "plans", "تعديل خصائص الباقات وحالتها"),
    ("routers.create", "إضافة الراوترات", "routers", "تسجيل راوتر جديد"),
    ("routers.update", "تعديل الراوترات", "routers", "تعديل بيانات الراوتر"),
    ("pos.create", "إضافة نقاط البيع", "pos", "إنشاء نقطة بيع جديدة"),
    ("pos.update", "تعديل نقاط البيع", "pos", "تعديل بيانات نقطة البيع"),
    ("finance.create", "تسجيل الحركات المالية", "finance", "إضافة سداد أو عمولة أو تسوية إلى حساب نقطة البيع"),
    ("printing.view", "عرض سجل الطباعة", "printing", "عرض عمليات الطباعة السابقة"),
    ("printing.create", "تنفيذ الطباعة", "printing", "إنشاء عملية طباعة أصلية وتخصيص الكروت"),
    ("printing.reprint", "إعادة الطباعة", "printing", "إعادة طباعة كروت سبق تخصيصها"),
    ("printing.credentials", "عرض بيانات الطباعة", "printing", "استلام بيانات دخول الكروت ضمن نتيجة الطباعة"),
    ("templates.view", "عرض تصاميم الكروت", "templates", "مشاهدة القوالب ومعاينتها"),
    ("templates.create", "إضافة تصاميم الكروت", "templates", "إنشاء قالب بطاقة جديد"),
    ("templates.update", "تعديل تصاميم الكروت", "templates", "تعديل القوالب وربطها بالباقة"),
    ("templates.delete", "حذف تصاميم الكروت", "templates", "حذف قالب غير افتراضي وغير مرتبط بسجلات"),
    ("templates.manage", "إدارة تصاميم الكروت", "templates", "منح صلاحيات عرض وإنشاء وتعديل وحذف القوالب"),
]


ROLE_GRANTS = {
    # Existing manage grants continue to imply supported create/update actions.
    # Credential disclosure remains a separate, explicit grant.
    "manager": ["cards.credentials", "printing.credentials", "templates.manage"],
    "operator": ["cards.credentials", "printing.view", "printing.credentials", "templates.view"],
    "viewer": ["printing.view", "templates.view"],
}


def upgrade() -> None:
    bind = op.get_bind()

    for code, name, module, description in NEW_PERMISSIONS:
        exists = bind.execute(
            sa.text("SELECT id FROM permissions WHERE code = :code"),
            {"code": code},
        ).scalar_one_or_none()
        if exists is None:
            bind.execute(
                sa.text(
                    "INSERT INTO permissions (code, name, module, description) "
                    "VALUES (:code, :name, :module, :description)"
                ),
                {"code": code, "name": name, "module": module, "description": description},
            )

    permission_ids = {
        row["code"]: row["id"]
        for row in bind.execute(
            sa.text("SELECT id, code FROM permissions WHERE code IN :codes")
            .bindparams(sa.bindparam("codes", expanding=True)),
            {"codes": [item[0] for item in NEW_PERMISSIONS]},
        ).mappings()
    }
    role_ids = {
        row["code"]: row["id"]
        for row in bind.execute(
            sa.text("SELECT id, code FROM roles WHERE code IN ('manager', 'operator', 'viewer')")
        ).mappings()
    }

    for role_code, permission_codes in ROLE_GRANTS.items():
        role_id = role_ids.get(role_code)
        if role_id is None:
            continue
        for permission_code in permission_codes:
            permission_id = permission_ids[permission_code]
            exists = bind.execute(
                sa.text(
                    "SELECT 1 FROM role_permissions "
                    "WHERE role_id = :role_id AND permission_id = :permission_id"
                ),
                {"role_id": role_id, "permission_id": permission_id},
            ).scalar_one_or_none()
            if exists is None:
                bind.execute(
                    sa.text(
                        "INSERT INTO role_permissions (role_id, permission_id) "
                        "VALUES (:role_id, :permission_id)"
                    ),
                    {"role_id": role_id, "permission_id": permission_id},
                )


def downgrade() -> None:
    codes = [item[0] for item in NEW_PERMISSIONS]
    bind = op.get_bind()
    permission_ids = bind.execute(
        sa.text("SELECT id FROM permissions WHERE code IN :codes")
        .bindparams(sa.bindparam("codes", expanding=True)),
        {"codes": codes},
    ).scalars().all()
    if permission_ids:
        bind.execute(
            sa.text("DELETE FROM role_permissions WHERE permission_id IN :permission_ids")
            .bindparams(sa.bindparam("permission_ids", expanding=True)),
            {"permission_ids": permission_ids},
        )
        bind.execute(
            sa.text("DELETE FROM permissions WHERE id IN :permission_ids")
            .bindparams(sa.bindparam("permission_ids", expanding=True)),
            {"permission_ids": permission_ids},
        )
