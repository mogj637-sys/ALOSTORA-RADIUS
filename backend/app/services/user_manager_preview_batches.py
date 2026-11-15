"""Compose the bounded page runner with transactional preview persistence.

The caller supplies a source reader. This module does not connect to RouterOS or
claim that RouterOS pagination is available; it only coordinates a reader that
already satisfies the bounded SourcePage contract.
"""
from __future__ import annotations

from typing import Callable, Mapping, Any
from uuid import UUID

from app.db.session import SessionLocal
from app.models.user_manager import UserManagerSyncRun
from app.services.user_manager_batch_persistence import (
    BatchPersistenceError,
    persist_user_manager_preview_page,
)
from app.services.user_manager_batches import (
    BatchPolicy,
    BatchResult,
    SourcePage,
    run_bounded_batches,
)


def run_user_manager_preview_batches(
    *,
    sync_run_id: UUID,
    fetch_page: Callable[[str | None, int], SourcePage],
    policy: BatchPolicy | None = None,
) -> BatchResult:
    """Resume a preview run from its DB checkpoint and persist every page atomically.

    A new DB session is used for each page commit. This keeps the transaction
    short and ensures the page data and its continuation checkpoint are committed
    together. The supplied fetch_page must enforce its limit at the source.
    """
    with SessionLocal() as db:
        run = db.get(UserManagerSyncRun, sync_run_id)
        if run is None:
            raise BatchPersistenceError("sync run does not exist")
        if run.run_type != "preview":
            raise BatchPersistenceError("only preview runs can be resumed")
        if (run.checkpoint or {}).get("mode") == "single_user_preview":
            raise BatchPersistenceError("single-user preview runs cannot be resumed as batches")
        checkpoint = dict(run.checkpoint or {})

    def persist_page(records: Any, next_checkpoint: dict[str, Any]) -> None:
        with SessionLocal() as page_db:
            persist_user_manager_preview_page(
                page_db,
                sync_run_id=sync_run_id,
                records=records,
                checkpoint=next_checkpoint,
            )

    return run_bounded_batches(
        fetch_page=fetch_page,
        persist_page=persist_page,
        checkpoint=checkpoint,
        policy=policy,
    )
