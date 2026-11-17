"""store the RouterOS API transport mode explicitly

Revision ID: 0012_router_api_tls
Revises: 0011_um_credential_modes
"""
from alembic import op
import sqlalchemy as sa

revision = "0012_router_api_tls"
down_revision = "0011_um_credential_modes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "routers",
        sa.Column(
            "api_use_ssl",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    # Preserve the old default-port inference for existing installations.
    op.execute(
        "UPDATE routers SET api_use_ssl = "
        "CASE WHEN api_port = 8729 THEN TRUE ELSE FALSE END"
    )

def downgrade() -> None:
    op.drop_column("routers", "api_use_ssl")
