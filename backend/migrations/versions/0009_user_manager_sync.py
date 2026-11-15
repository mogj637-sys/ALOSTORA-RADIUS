"""add User Manager import tracking tables

Revision ID: 0009_user_manager_sync
Revises: 0008_plan_commission
"""
from alembic import op
import sqlalchemy as sa

revision = "0009_user_manager_sync"
down_revision = "0008_plan_commission"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_manager_sync_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("router_id", sa.Integer(), sa.ForeignKey("routers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("run_type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("routeros_version", sa.String(30), nullable=True),
        sa.Column("discovered_users", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("discovered_profiles", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("discovered_sessions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_cards", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_records", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("conflicted_records", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_records", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("checkpoint", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("source_summary", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("error_summary", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_um_sync_runs_router_created", "user_manager_sync_runs", ["router_id", "created_at"])
    op.create_index("ix_um_sync_runs_status", "user_manager_sync_runs", ["status"])

    op.create_table(
        "user_manager_card_sources",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("router_id", sa.Integer(), sa.ForeignKey("routers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("external_user_id", sa.String(160), nullable=False),
        sa.Column("username", sa.String(120), nullable=False),
        sa.Column("card_id", sa.Uuid(), sa.ForeignKey("cards.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("source_profile_id", sa.String(160), nullable=True),
        sa.Column("source_status", sa.String(40), nullable=True),
        sa.Column("credential_state", sa.String(30), nullable=False, server_default="unknown"),
        sa.Column("last_counters", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("raw_snapshot", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("router_id", "external_user_id", name="uq_um_card_source_external_user"),
        sa.UniqueConstraint("card_id", name="uq_um_card_source_card"),
    )
    op.create_index("ix_um_card_source_username", "user_manager_card_sources", ["username"])


def downgrade() -> None:
    op.drop_index("ix_um_card_source_username", table_name="user_manager_card_sources")
    op.drop_table("user_manager_card_sources")
    op.drop_index("ix_um_sync_runs_status", table_name="user_manager_sync_runs")
    op.drop_index("ix_um_sync_runs_router_created", table_name="user_manager_sync_runs")
    op.drop_table("user_manager_sync_runs")
