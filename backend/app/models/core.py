import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    false,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False
    )


class Plan(TimestampMixin, Base):
    __tablename__ = "plans"
    __table_args__ = (
        CheckConstraint("price >= 0", name="ck_plans_price_nonnegative"),
        CheckConstraint("commission_value >= 0", name="ck_plans_commission_nonnegative"),
        CheckConstraint("commission_type != 'percentage' OR commission_value <= 100", name="ck_plans_commission_percentage_max"),
        CheckConstraint("commission_type != 'fixed' OR commission_value <= price", name="ck_plans_fixed_commission_not_above_price"),
        CheckConstraint(
            "data_limit_bytes IS NULL OR data_limit_bytes > 0",
            name="ck_plans_data_limit_positive_or_unlimited",
        ),
        CheckConstraint(
            "session_time_limit_seconds IS NULL OR session_time_limit_seconds > 0",
            name="ck_plans_session_time_positive_or_unlimited",
        ),
        CheckConstraint(
            "validity_period_seconds IS NULL OR validity_period_seconds > 0",
            name="ck_plans_validity_positive_or_unlimited",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    commission_type: Mapped[str] = mapped_column(String(20), nullable=False, default="none")
    commission_value: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    # NULL means unlimited. Zero is deliberately not used for unlimited limits.
    data_limit_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    session_time_limit_seconds: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # Starts at first successful authentication; counts wall-clock time continuously.
    validity_period_seconds: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    speed_profile: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class PointOfSale(TimestampMixin, Base):
    __tablename__ = "points_of_sale"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    contact_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Router(TimestampMixin, Base):
    __tablename__ = "routers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    nas_identifier: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    management_host: Mapped[str] = mapped_column(String(255), nullable=False)
    radius_client_address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    api_port: Mapped[int] = mapped_column(Integer, nullable=False, default=8728)
    api_use_ssl: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    api_username: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # Router API and RADIUS shared secrets are stored only as ciphertext.
    api_secret_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    radius_secret_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    routeros_version: Mapped[str | None] = mapped_column(String(30), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Card(TimestampMixin, Base):
    __tablename__ = "cards"
    __table_args__ = (
        CheckConstraint("price_snapshot >= 0", name="ck_cards_price_snapshot_nonnegative"),
        CheckConstraint("used_seconds >= 0", name="ck_cards_used_seconds_nonnegative"),
        CheckConstraint("upload_bytes >= 0", name="ck_cards_upload_bytes_nonnegative"),
        CheckConstraint("download_bytes >= 0", name="ck_cards_download_bytes_nonnegative"),
        Index("ix_cards_status_expires_at", "status", "expires_at"),
        Index("ix_cards_pos_status", "assigned_pos_id", "status"),
        Index("ix_cards_radius_auth_reserved_until", "radius_auth_reserved_until"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    serial_number: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    username: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    # Card passwords are encrypted at rest and decrypted only during protected RADIUS authorization.
    credential_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    credential_scheme: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    card_type: Mapped[str] = mapped_column(String(30), nullable=False, default="standard")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="generated")
    is_free: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False)
    plan_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    price_snapshot: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)

    assigned_pos_id: Mapped[int | None] = mapped_column(
        ForeignKey("points_of_sale.id", ondelete="RESTRICT"), nullable=True
    )
    allocated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    radius_auth_reserved_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    used_seconds: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    upload_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    download_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    plan: Mapped[Plan] = relationship()
    assigned_pos: Mapped[PointOfSale | None] = relationship()


class PrintJob(TimestampMixin, Base):
    __tablename__ = "print_jobs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    idempotency_key: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    point_of_sale_id: Mapped[int | None] = mapped_column(
        ForeignKey("points_of_sale.id", ondelete="RESTRICT"), nullable=True
    )
    template_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    card_count: Mapped[int] = mapped_column(Integer, nullable=False)
    is_reprint: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    requested_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    items: Mapped[list["PrintJobItem"]] = relationship(back_populates="print_job")


class PrintJobItem(Base):
    __tablename__ = "print_job_items"
    __table_args__ = (
        UniqueConstraint("print_job_id", "card_id", name="uq_print_job_item_card"),
        Index("ix_print_job_items_card", "card_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    print_job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("print_jobs.id", ondelete="RESTRICT"), nullable=False
    )
    card_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cards.id", ondelete="RESTRICT"), nullable=False
    )
    serial_number_snapshot: Mapped[str] = mapped_column(String(80), nullable=False)
    username_snapshot: Mapped[str] = mapped_column(String(120), nullable=False)
    is_free: Mapped[bool] = mapped_column(Boolean, nullable=False)
    price_snapshot: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    print_job: Mapped[PrintJob] = relationship(back_populates="items")


class PosInventoryMovement(Base):
    __tablename__ = "pos_inventory_movements"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_pos_movement_idempotency_key"),
        Index("ix_pos_movements_pos_created", "point_of_sale_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    point_of_sale_id: Mapped[int] = mapped_column(
        ForeignKey("points_of_sale.id", ondelete="RESTRICT"), nullable=False
    )
    card_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cards.id", ondelete="RESTRICT"), nullable=False
    )
    print_job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("print_jobs.id", ondelete="RESTRICT"), nullable=True
    )
    movement_type: Mapped[str] = mapped_column(String(30), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CardEvent(Base):
    __tablename__ = "card_events"
    __table_args__ = (
        Index("ix_card_events_card_created", "card_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    card_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cards.id", ondelete="RESTRICT"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    details: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    actor: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class RadiusSession(Base):
    __tablename__ = "radius_sessions"
    __table_args__ = (
        UniqueConstraint("router_id", "acct_session_id", name="uq_radius_router_session"),
        Index("ix_radius_sessions_card_active", "card_id", "stopped_at"),
        Index("ix_radius_sessions_started_at", "started_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    card_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cards.id", ondelete="RESTRICT"), nullable=False
    )
    router_id: Mapped[int] = mapped_column(
        ForeignKey("routers.id", ondelete="RESTRICT"), nullable=False
    )
    acct_session_id: Mapped[str] = mapped_column(String(150), nullable=False)
    framed_ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    calling_station_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_update_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    input_octets: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    output_octets: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    session_time_seconds: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    last_packet_fingerprint: Mapped[str | None] = mapped_column(String(128), nullable=True)
    card_status_before_session: Mapped[str | None] = mapped_column(String(30), nullable=True)


class PosAccountEntry(Base):
    """Append-only financial ledger for a point of sale."""
    __tablename__ = "pos_account_entries"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_pos_account_entry_amount_positive"),
        UniqueConstraint("idempotency_key", name="uq_pos_account_entry_idempotency"),
        Index("ix_pos_account_entries_pos_created", "point_of_sale_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    point_of_sale_id: Mapped[int] = mapped_column(
        ForeignKey("points_of_sale.id", ondelete="RESTRICT"), nullable=False
    )
    entry_type: Mapped[str] = mapped_column(String(30), nullable=False)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
