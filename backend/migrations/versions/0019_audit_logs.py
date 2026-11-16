"""create administrative audit log

Revision ID: 0019_audit_logs
Revises: 0018_role_permissions
"""
from alembic import op
import sqlalchemy as sa

revision = "0019_audit_logs"
down_revision = "0018_role_permissions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("actor_username", sa.String(length=80), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.String(length=120), nullable=True),
        sa.Column("summary", sa.String(length=300), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])
    op.create_index("ix_audit_logs_actor_created", "audit_logs", ["actor_id", "created_at"])
    op.create_index("ix_audit_logs_entity", "audit_logs", ["entity_type", "entity_id"])
    op.create_table(
        "audit_permission_seed",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("permission_id", sa.Integer(), nullable=False),
    )
    bind = op.get_bind()
    bind.execute(sa.text("INSERT INTO permissions (code, name, module, description) VALUES ('audit.view', 'عرض سجل العمليات', 'audit', 'مشاهدة سجل أنشطة النظام')"))
    permission_id = bind.execute(sa.text("SELECT id FROM permissions WHERE code = 'audit.view'")).scalar_one()
    manager_id = bind.execute(sa.text("SELECT id FROM roles WHERE code = 'manager'")).scalar_one_or_none()
    if manager_id is not None:
        bind.execute(sa.text("INSERT INTO role_permissions (role_id, permission_id) VALUES (:role_id, :permission_id)"), {"role_id": manager_id, "permission_id": permission_id})
    op.drop_table("audit_permission_seed")


def downgrade() -> None:
    op.execute("DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE code = 'audit.view')")
    op.execute("DELETE FROM permissions WHERE code = 'audit.view'")
    op.drop_index("ix_audit_logs_entity", table_name="audit_logs")
    op.drop_index("ix_audit_logs_actor_created", table_name="audit_logs")
    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_table("audit_logs")
