"""make credential disclosure opt-in and complete operator card creation access

Revision ID: 0025_credential_access_opt_in
Revises: 0024_granular_permissions
"""
from alembic import op
import sqlalchemy as sa

revision = "0025_credential_access_opt_in"
down_revision = "0024_granular_permissions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    # Password visibility is a sensitive capability and must be granted explicitly.
    bind.execute(
        sa.text(
            "DELETE FROM role_permissions "
            "WHERE role_id = (SELECT id FROM roles WHERE code = 'manager') "
            "AND permission_id IN ("
            "SELECT id FROM permissions "
            "WHERE code IN ('cards.credentials', 'printing.credentials')"
            ")"
        )
    )

    # Operators who can create cards need to read the plan catalogue used by the form.
    bind.execute(
        sa.text(
            "INSERT INTO role_permissions (role_id, permission_id) "
            "SELECT roles.id, permissions.id "
            "FROM roles CROSS JOIN permissions "
            "WHERE roles.code = 'operator' AND permissions.code = 'plans.view' "
            "ON CONFLICT DO NOTHING"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()

    # Restore the manager's original grants from the granular-permissions migration.
    bind.execute(
        sa.text(
            "INSERT INTO role_permissions (role_id, permission_id) "
            "SELECT roles.id, permissions.id "
            "FROM roles CROSS JOIN permissions "
            "WHERE roles.code = 'manager' "
            "AND permissions.code IN ('cards.credentials', 'printing.credentials') "
            "ON CONFLICT DO NOTHING"
        )
    )
    bind.execute(
        sa.text(
            "DELETE FROM role_permissions "
            "WHERE role_id = (SELECT id FROM roles WHERE code = 'operator') "
            "AND permission_id = (SELECT id FROM permissions WHERE code = 'plans.view')"
        )
    )
