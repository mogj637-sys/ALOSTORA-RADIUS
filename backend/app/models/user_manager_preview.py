from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, UniqueConstraint, Uuid, BigInteger, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserManagerImportPreview(Base):
    """Immutable, per-run candidate row used to review an import before approval."""

    __tablename__ = "user_manager_import_previews"
    __table_args__ = (
        UniqueConstraint(
            "sync_run_id", "external_user_id",
            name="uq_um_import_preview_run_external_user",
        ),
        Index("ix_um_import_preview_run_classification", "sync_run_id", "classification"),
        Index("ix_um_import_preview_username", "username"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    sync_run_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("user_manager_sync_runs.id", ondelete="RESTRICT"), nullable=False
    )
    external_user_id: Mapped[str] = mapped_column(String(160), nullable=False)
    username: Mapped[str] = mapped_column(String(120), nullable=False)
    source_profile_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    classification: Mapped[str] = mapped_column(String(30), nullable=False)
    matched_card_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("cards.id", ondelete="RESTRICT"), nullable=True
    )
    safe_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    issues: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    source_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
