import secrets
from uuid import uuid4

import pytest

from app.db.session import SessionLocal
from app.models.user_manager import UserManagerSyncRun
from app.models.user_manager_preview import UserManagerImportPreview
from app.services.user_manager_batch_persistence import (
    BatchPersistenceError,
    persist_user_manager_preview_page,
)


def _create_preview_run(client, headers):
    response = client.post(
        "/api/v1/routers",
        headers=headers,
        json={
            "name": "UM batch " + secrets.token_hex(3),
            "nas_identifier": "um-batch-" + secrets.token_hex(4),
            "management_host": "192.0.2.77",
            "api_port": 8728,
            "api_username": "um-reader",
            "api_secret": "api-secret-" + secrets.token_hex(8),
            "radius_secret": "radius-secret-" + secrets.token_hex(8),
        },
    )
    assert response.status_code == 201, response.text
    router_id = response.json()["id"]
    run_id = uuid4()
    db = SessionLocal()
    try:
        db.add(UserManagerSyncRun(
            id=run_id,
            router_id=router_id,
            run_type="preview",
            status="scanning",
            checkpoint={},
        ))
        db.commit()
    finally:
        db.close()
    return run_id


def _checkpoint(*, cursor="cursor-2", records=1, pages=1, complete=False):
    return {
        "cursor": cursor,
        "processed_records": records,
        "processed_pages": pages,
        "cursor_history": [],
        "source_complete": complete,
    }


def test_preview_page_and_checkpoint_commit_atomically_and_replay_idempotently(owner_client):
    client, headers, _ = owner_client
    run_id = _create_preview_run(client, headers)
    records = [{
        "external_id": "*BATCH1",
        "username": "batch-voucher-1",
        "actual_profile": "basic",
        "password": "never-store-this",
        "usage": {"download_used_bytes": "1024"},
    }]
    checkpoint = _checkpoint()

    db = SessionLocal()
    try:
        inserted = persist_user_manager_preview_page(
            db, sync_run_id=run_id, records=records, checkpoint=checkpoint
        )
        assert inserted == 1
    finally:
        db.close()

    db = SessionLocal()
    try:
        inserted_again = persist_user_manager_preview_page(
            db, sync_run_id=run_id, records=records, checkpoint=checkpoint
        )
        assert inserted_again == 0
    finally:
        db.close()

    verify = SessionLocal()
    try:
        run = verify.get(UserManagerSyncRun, run_id)
        previews = verify.query(UserManagerImportPreview).filter_by(sync_run_id=run_id).all()
        assert run.checkpoint == checkpoint
        assert run.discovered_users == 1
        assert len(previews) == 1
        assert previews[0].username == "batch-voucher-1"
        assert previews[0].safe_snapshot["usage"]["download_used_bytes"] == "1024"
        assert "password" not in repr(previews[0].safe_snapshot).lower()
        assert "never-store-this" not in repr(previews[0])
    finally:
        verify.close()


def test_preview_page_rejects_changed_source_record_for_same_external_id(owner_client):
    client, headers, _ = owner_client
    run_id = _create_preview_run(client, headers)
    first = [{"external_id": "*BATCH2", "username": "batch-voucher-2", "comment": "first"}]
    db = SessionLocal()
    try:
        persist_user_manager_preview_page(
            db, sync_run_id=run_id, records=first, checkpoint=_checkpoint()
        )
    finally:
        db.close()

    changed = [{"external_id": "*BATCH2", "username": "batch-voucher-2", "comment": "changed"}]
    db = SessionLocal()
    try:
        with pytest.raises(BatchPersistenceError, match="changed within"):
            persist_user_manager_preview_page(
                db, sync_run_id=run_id, records=changed, checkpoint=_checkpoint()
            )
    finally:
        db.close()

    verify = SessionLocal()
    try:
        run = verify.get(UserManagerSyncRun, run_id)
        previews = verify.query(UserManagerImportPreview).filter_by(sync_run_id=run_id).all()
        assert run.checkpoint == _checkpoint()
        assert len(previews) == 1
        assert previews[0].safe_snapshot["comment"] == "first"
    finally:
        verify.close()


def test_preview_page_rolls_back_rows_when_flush_fails(owner_client, monkeypatch):
    client, headers, _ = owner_client
    run_id = _create_preview_run(client, headers)
    db = SessionLocal()

    def fail_flush(*_args, **_kwargs):
        raise RuntimeError("simulated database flush failure")

    monkeypatch.setattr(db, "flush", fail_flush)
    try:
        with pytest.raises(RuntimeError, match="flush failure"):
            persist_user_manager_preview_page(
                db,
                sync_run_id=run_id,
                records=[{"external_id": "*BATCH3", "username": "batch-voucher-3"}],
                checkpoint=_checkpoint(),
            )
    finally:
        db.close()

    verify = SessionLocal()
    try:
        run = verify.get(UserManagerSyncRun, run_id)
        previews = verify.query(UserManagerImportPreview).filter_by(sync_run_id=run_id).all()
        assert run.checkpoint == {}
        assert previews == []
    finally:
        verify.close()


def test_preview_page_rejects_duplicate_or_missing_source_identity_before_write(owner_client):
    client, headers, _ = owner_client
    run_id = _create_preview_run(client, headers)
    db = SessionLocal()
    try:
        with pytest.raises(BatchPersistenceError, match="duplicate external ID"):
            persist_user_manager_preview_page(
                db,
                sync_run_id=run_id,
                records=[
                    {"external_id": "*DUP", "username": "one"},
                    {"external_id": "*DUP", "username": "two"},
                ],
                checkpoint=_checkpoint(records=2),
            )
    finally:
        db.close()

    db = SessionLocal()
    try:
        with pytest.raises(BatchPersistenceError, match="stable external ID"):
            persist_user_manager_preview_page(
                db,
                sync_run_id=run_id,
                records=[{"username": "missing-id"}],
                checkpoint=_checkpoint(),
            )
    finally:
        db.close()

    verify = SessionLocal()
    try:
        run = verify.get(UserManagerSyncRun, run_id)
        previews = verify.query(UserManagerImportPreview).filter_by(sync_run_id=run_id).all()
        assert run.checkpoint == {}
        assert previews == []
    finally:
        verify.close()


def test_preview_page_requires_checkpoint_delta_to_match_exact_page(owner_client):
    client, headers, _ = owner_client
    run_id = _create_preview_run(client, headers)
    db = SessionLocal()
    try:
        with pytest.raises(BatchPersistenceError, match="exactly one"):
            persist_user_manager_preview_page(
                db,
                sync_run_id=run_id,
                records=[{"external_id": "*BATCH4", "username": "batch-voucher-4"}],
                checkpoint=_checkpoint(records=2, pages=1),
            )
    finally:
        db.close()
