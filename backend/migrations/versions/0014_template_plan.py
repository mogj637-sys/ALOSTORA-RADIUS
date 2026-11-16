"""associate card templates with package plans

Revision ID: 0014_template_plan
Revises: 0013_plan_options
"""
from alembic import op
import sqlalchemy as sa

revision = "0014_template_plan"
down_revision = "0013_plan_options"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "card_templates",
        sa.Column("plan_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_card_templates_plan_id_plans",
        "card_templates",
        "plans",
        ["plan_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_card_templates_plan_id", "card_templates", ["plan_id"])


def downgrade() -> None:
    op.drop_index("ix_card_templates_plan_id", table_name="card_templates")
    op.drop_constraint("fk_card_templates_plan_id_plans", "card_templates", type_="foreignkey")
    op.drop_column("card_templates", "plan_id")
