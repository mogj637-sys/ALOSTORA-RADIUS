"""add persistent voucher card templates

Revision ID: 0012_card_templates
Revises: 0011_um_credential_modes
"""
from alembic import op
import sqlalchemy as sa

revision = "0012_card_templates"
down_revision = "0011_um_credential_modes"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "card_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=80), nullable=False, unique=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("width_mm", sa.Numeric(6, 2), nullable=False, server_default="90"),
        sa.Column("height_mm", sa.Numeric(6, 2), nullable=False, server_default="50"),
        sa.Column("background_color", sa.String(length=7), nullable=False, server_default="#ffffff"),
        sa.Column("text_color", sa.String(length=7), nullable=False, server_default="#173b2d"),
        sa.Column("layout", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("width_mm > 0 AND width_mm <= 300", name="ck_card_templates_width"),
        sa.CheckConstraint("height_mm > 0 AND height_mm <= 300", name="ck_card_templates_height"),
    )
    op.bulk_insert(
        sa.table(
            "card_templates",
            sa.column("code", sa.String),
            sa.column("name", sa.String),
            sa.column("width_mm", sa.Numeric),
            sa.column("height_mm", sa.Numeric),
            sa.column("background_color", sa.String),
            sa.column("text_color", sa.String),
            sa.column("layout", sa.JSON),
            sa.column("is_default", sa.Boolean),
        ),
        [
            {"code": "classic-green", "name": "القالب الأخضر", "width_mm": 90, "height_mm": 50, "background_color": "#e9f6ef", "text_color": "#174c37", "layout": {}, "is_default": True},
            {"code": "classic-blue", "name": "القالب الأزرق", "width_mm": 90, "height_mm": 50, "background_color": "#eaf3fc", "text_color": "#244a70", "layout": {}, "is_default": False},
            {"code": "compact", "name": "القالب المختصر", "width_mm": 75, "height_mm": 40, "background_color": "#ffffff", "text_color": "#173b2d", "layout": {}, "is_default": False},
        ],
    )

def downgrade() -> None:
    op.drop_table("card_templates")
