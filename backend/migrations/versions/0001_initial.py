"""create initial core schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-11-15
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(50), nullable=False, unique=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("data_limit_bytes", sa.BigInteger(), nullable=True),
        sa.Column("session_time_limit_seconds", sa.BigInteger(), nullable=True),
        sa.Column("validity_period_seconds", sa.BigInteger(), nullable=True),
        sa.Column("speed_profile", sa.String(100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("price >= 0", name="ck_plans_price_nonnegative"),
        sa.CheckConstraint("data_limit_bytes IS NULL OR data_limit_bytes > 0", name="ck_plans_data_limit_positive_or_unlimited"),
        sa.CheckConstraint("session_time_limit_seconds IS NULL OR session_time_limit_seconds > 0", name="ck_plans_session_time_positive_or_unlimited"),
        sa.CheckConstraint("validity_period_seconds IS NULL OR validity_period_seconds > 0", name="ck_plans_validity_positive_or_unlimited"),
    )

    op.create_table(
        "points_of_sale",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(50), nullable=False, unique=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("contact_name", sa.String(150), nullable=True),
        sa.Column("phone", sa.String(40), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "routers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("nas_identifier", sa.String(150), nullable=False, unique=True),
        sa.Column("management_host", sa.String(255), nullable=False),
        sa.Column("api_port", sa.Integer(), nullable=False),
        sa.Column("api_username", sa.String(120), nullable=True),
        sa.Column("api_secret_encrypted", sa.Text(), nullable=True),
        sa.Column("radius_secret_encrypted", sa.Text(), nullable=False),
        sa.Column("routeros_version", sa.String(30), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "cards",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("serial_number", sa.String(80), nullable=False, unique=True),
        sa.Column("username", sa.String(120), nullable=False, unique=True),
        sa.Column("credential_ciphertext", sa.Text(), nullable=False),
        sa.Column("credential_scheme", sa.String(30), nullable=False),
        sa.Column("card_type", sa.String(30), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("is_free", sa.Boolean(), nullable=False),
        sa.Column("plan_id", sa.Integer(), sa.ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("plan_snapshot", sa.JSON(), nullable=False),
        sa.Column("price_snapshot", sa.Numeric(12, 2), nullable=False),
        sa.Column("assigned_pos_id", sa.Integer(), sa.ForeignKey("points_of_sale.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("allocated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("used_seconds", sa.BigInteger(), nullable=False),
        sa.Column("upload_bytes", sa.BigInteger(), nullable=False),
        sa.Column("download_bytes", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("price_snapshot >= 0", name="ck_cards_price_snapshot_nonnegative"),
        sa.CheckConstraint("used_seconds >= 0", name="ck_cards_used_seconds_nonnegative"),
        sa.CheckConstraint("upload_bytes >= 0", name="ck_cards_upload_bytes_nonnegative"),
        sa.CheckConstraint("download_bytes >= 0", name="ck_cards_download_bytes_nonnegative"),
    )
    op.create_index("ix_cards_status_expires_at", "cards", ["status", "expires_at"])
    op.create_index("ix_cards_pos_status", "cards", ["assigned_pos_id", "status"])

    op.create_table(
        "print_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("idempotency_key", sa.String(120), nullable=False, unique=True),
        sa.Column("point_of_sale_id", sa.Integer(), sa.ForeignKey("points_of_sale.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("template_code", sa.String(80), nullable=True),
        sa.Column("card_count", sa.Integer(), nullable=False),
        sa.Column("is_reprint", sa.Boolean(), nullable=False),
        sa.Column("requested_by", sa.String(120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "pos_inventory_movements",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("point_of_sale_id", sa.Integer(), sa.ForeignKey("points_of_sale.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("card_id", sa.Uuid(), sa.ForeignKey("cards.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("print_job_id", sa.Uuid(), sa.ForeignKey("print_jobs.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("movement_type", sa.String(30), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("idempotency_key", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_pos_movement_idempotency_key"),
    )
    op.create_index("ix_pos_movements_pos_created", "pos_inventory_movements", ["point_of_sale_id", "created_at"])

    op.create_table(
        "card_events",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("card_id", sa.Uuid(), sa.ForeignKey("cards.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("actor", sa.String(120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_card_events_card_created", "card_events", ["card_id", "created_at"])

    op.create_table(
        "radius_sessions",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("card_id", sa.Uuid(), sa.ForeignKey("cards.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("router_id", sa.Integer(), sa.ForeignKey("routers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("acct_session_id", sa.String(150), nullable=False),
        sa.Column("framed_ip_address", sa.String(45), nullable=True),
        sa.Column("calling_station_id", sa.String(100), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_update_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("input_octets", sa.BigInteger(), nullable=False),
        sa.Column("output_octets", sa.BigInteger(), nullable=False),
        sa.Column("session_time_seconds", sa.BigInteger(), nullable=False),
        sa.Column("last_packet_fingerprint", sa.String(128), nullable=True),
        sa.UniqueConstraint("router_id", "acct_session_id", name="uq_radius_router_session"),
    )
    op.create_index("ix_radius_sessions_card_active", "radius_sessions", ["card_id", "stopped_at"])
    op.create_index("ix_radius_sessions_started_at", "radius_sessions", ["started_at"])


def downgrade() -> None:
    op.drop_index("ix_radius_sessions_started_at", table_name="radius_sessions")
    op.drop_index("ix_radius_sessions_card_active", table_name="radius_sessions")
    op.drop_table("radius_sessions")
    op.drop_index("ix_card_events_card_created", table_name="card_events")
    op.drop_table("card_events")
    op.drop_index("ix_pos_movements_pos_created", table_name="pos_inventory_movements")
    op.drop_table("pos_inventory_movements")
    op.drop_table("print_jobs")
    op.drop_index("ix_cards_pos_status", table_name="cards")
    op.drop_index("ix_cards_status_expires_at", table_name="cards")
    op.drop_table("cards")
    op.drop_table("routers")
    op.drop_table("points_of_sale")
    op.drop_table("plans")
