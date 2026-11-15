from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserManagerSyncRun(Base):
    """Auditable execution record for a read-only User Manager sync."""

    __tablename__ = "user_manager_sync_runs"
    __table_args__ = (
        Index("ix_um_sync_runs_router_created", "router_id", "created_at"),
        Index("ix_um_sync_runs_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    router_id: Mapped[int] = mapped_column(
        ForeignKey("routers.id", ondelete="RESTRICT"), nullable=False
    )
    run_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    routeros_version: Mapped[str | None] = mapped_column(String(30), nullable=True)
    discovered_users: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    discovered_profiles: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    discovered_sessions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_cards: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    conflicted_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    checkpoint: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    source_summary: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    error_summary: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class UserManagerCardSource(Base):
    """Stable mapping from a User Manager user to one ALOSTORA card."""

    __tablename__ = "user_manager_card_sources"
    __table_args__ = (
        UniqueConstraint(
            "router_id", "external_user_id", name="uq_um_card_source_external_user"
        ),
        UniqueConstraint("card_id", name="uq_um_card_source_card"),
        Index("ix_um_card_source_username", "username"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    router_id: Mapped[int] = mapped_column(
        ForeignKey("routers.id", ondelete="RESTRICT"), nullable=False
    )
    external_user_id: Mapped[str] = mapped_column(String(160), nullable=False)
    username: Mapped[str] = mapped_column(String(120), nullable=False)
    card_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("cards.id", ondelete="RESTRICT"), nullable=True
    )
    source_profile_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    source_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    credential_state: Mapped[str] = mapped_column(
        String(30), nullable=False, default="unknown"
    )
    last_counters: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    raw_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False
    )
