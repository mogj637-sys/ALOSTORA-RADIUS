"""Transactional persistence for bounded User Manager preview pages.

A fresh SQLAlchemy Session is required. Each call commits preview rows and the
run checkpoint in one transaction; any exception rolls both back.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.core import Card
from app.models.user_manager import UserManagerCardSource, UserManagerSyncRun
from app.models.user_manager_preview import UserManagerImportPreview
from app.services.user_manager_preview import build_user_manager_preview


class BatchPersistenceError(RuntimeError):
    """Raised when a preview page cannot be safely committed."""


def _checkpoint_count(checkpoint: Mapping[str, Any], key: str) -> int:
    value = checkpoint.get(key, 0)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise BatchPersistenceError(f"checkpoint {key} must be a non-negative integer")
    return value


def persist_user_manager_preview_page(
    db: Session,
    *,
    sync_run_id: UUID,
    records: Sequence[Mapping[str, Any]],
    checkpoint: Mapping[str, Any],
) -> int:
    """Persist one preview page and its checkpoint atomically.

    The source page must have stable, unique external IDs. Replaying an identical
    page is idempotent. Reusing an external ID with changed source content in the
    same run is rejected rather than silently overwriting an immutable preview.
    """
    if not isinstance(checkpoint, Mapping):
        raise BatchPersistenceError("checkpoint must be an object")
    next_records = _checkpoint_count(checkpoint, "processed_records")
    next_pages = _checkpoint_count(checkpoint, "processed_pages")
    if not isinstance(checkpoint.get("source_complete", False), bool):
        raise BatchPersistenceError("checkpoint source_complete must be boolean")
    history = checkpoint.get("cursor_history", [])
    if not isinstance(history, list) or any(
        not isinstance(cursor, str) or not cursor for cursor in history
    ):
        raise BatchPersistenceError("checkpoint cursor_history is invalid")
    if checkpoint.get("source_complete") is False:
        cursor = checkpoint.get("cursor")
        if not isinstance(cursor, str) or not cursor:
            raise BatchPersistenceError("non-final checkpoint requires a continuation cursor")

    normalized_records: list[dict[str, Any]] = []
    external_ids: set[str] = set()
    usernames: set[str] = set()
    for source in records:
        if not isinstance(source, Mapping):
            raise BatchPersistenceError("every source record must be an object")
        record = dict(source)
        external_value = record.get("external_id", record.get(".id"))
        external_id = str(external_value).strip() if external_value is not None else ""
        if not external_id:
            raise BatchPersistenceError("source record is missing its stable external ID")
        if external_id in external_ids:
            raise BatchPersistenceError("source page contains a duplicate external ID")
        external_ids.add(external_id)
        username = str(record.get("username") or "").strip()
        if username:
            usernames.add(username)
        normalized_records.append(record)

    inserted = 0
    # This method owns the transaction. Call it with a fresh Session that has
    # no earlier autobegun transaction; the batch runner invokes it once/page.
    with db.begin():
        run = db.scalar(
            select(UserManagerSyncRun)
            .where(UserManagerSyncRun.id == sync_run_id)
            .with_for_update()
        )
        if run is None:
            raise BatchPersistenceError("sync run does not exist")
        if run.run_type != "preview":
            raise BatchPersistenceError("only preview runs can store preview pages")
        current_checkpoint = dict(run.checkpoint or {})
        if current_checkpoint.get("mode") == "single_user_preview":
            raise BatchPersistenceError("single-user preview runs cannot accept batch pages")

        previous_records = _checkpoint_count(current_checkpoint, "processed_records")
        previous_pages = _checkpoint_count(current_checkpoint, "processed_pages")
        if next_records < previous_records or next_pages < previous_pages:
            raise BatchPersistenceError("checkpoint counters cannot move backwards")
        exact_replay = (
            next_records == previous_records
            and next_pages == previous_pages
            and bool(current_checkpoint)
            and dict(checkpoint) == current_checkpoint
        )
        if not exact_replay and (
            next_pages != previous_pages + 1
            or next_records != previous_records + len(normalized_records)
        ):
            raise BatchPersistenceError(
                "checkpoint progress must match exactly one persisted source page"
            )

        existing_previews: dict[str, UserManagerImportPreview] = {}
        if external_ids:
            existing_previews = {
                row.external_user_id: row
                for row in db.scalars(
                    select(UserManagerImportPreview).where(
                        UserManagerImportPreview.sync_run_id == sync_run_id,
                        UserManagerImportPreview.external_user_id.in_(external_ids),
                    )
                )
            }

        card_rows = []
        if usernames:
            card_rows = db.execute(
                select(Card.username, Card.id).where(Card.username.in_(usernames))
            ).all()
        cards_by_username = {username: str(card_id) for username, card_id in card_rows}

        source_links: dict[str, str | None] = {}
        if external_ids:
            link_rows = db.execute(
                select(
                    UserManagerCardSource.external_user_id,
                    UserManagerCardSource.card_id,
                ).where(
                    UserManagerCardSource.router_id == run.router_id,
                    UserManagerCardSource.external_user_id.in_(external_ids),
                )
            ).all()
            source_links = {
                external_id: str(card_id) if card_id is not None else None
                for external_id, card_id in link_rows
            }

        classified = build_user_manager_preview(
            normalized_records,
            existing_cards_by_username=cards_by_username,
            source_links_by_external_id=source_links,
        )

        for candidate in classified:
            external_id = candidate["external_user_id"]
            if not external_id:
                raise BatchPersistenceError("classified preview has no external ID")
            if len(external_id) > 160:
                raise BatchPersistenceError("source external ID exceeds 160 characters")
            if candidate["username"] and len(candidate["username"]) > 120:
                raise BatchPersistenceError("source username exceeds 120 characters")
            if candidate["source_profile_id"] and len(candidate["source_profile_id"]) > 160:
                raise BatchPersistenceError("source profile ID exceeds 160 characters")
            existing = existing_previews.get(external_id)
            if existing is not None:
                if existing.source_fingerprint != candidate["source_fingerprint"]:
                    raise BatchPersistenceError(
                        "source record changed within the same preview run"
                    )
                continue

            matched_id = candidate["matched_card_id"]
            db.add(
                UserManagerImportPreview(
                    sync_run_id=sync_run_id,
                    external_user_id=external_id,
                    username=candidate["username"] or "",
                    source_profile_id=candidate["source_profile_id"],
                    classification=candidate["classification"],
                    credential_mode=candidate["credential_mode"],
                    credential_state=candidate["credential_state"],
                    matched_card_id=UUID(matched_id) if matched_id else None,
                    safe_snapshot=candidate["safe_snapshot"],
                    issues=candidate["issues"],
                    source_fingerprint=candidate["source_fingerprint"],
                )
            )
            inserted += 1

        # Flush inside the transaction so uniqueness/foreign-key failures roll
        # back together with the checkpoint update.
        db.flush()
        run.checkpoint = dict(checkpoint)
        run.discovered_users = max(run.discovered_users, next_records)
        run.status = (
            "preview_ready"
            if checkpoint.get("source_complete") is True
            else "scanning"
        )

    return inserted
