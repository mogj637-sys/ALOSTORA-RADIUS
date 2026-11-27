from concurrent.futures import ThreadPoolExecutor
from threading import Event, local
import secrets

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import selectinload

from app.api import admins as admins_api
from app.db.session import SessionLocal, engine
from app.models.auth import AdminUser, Role
from app.schemas.admins import AdminUserResponse, AdminUserUpdate
from app.schemas.routers import RouterResponse
from app.services.permissions import has_permission


def test_concurrent_owner_demotion_cannot_remove_the_last_active_owner(owner_client, monkeypatch):
    if engine.dialect.name != "postgresql":
        pytest.skip("FOR UPDATE concurrency semantics are verified on PostgreSQL")

    _, _, owner_username = owner_client
    suffix = secrets.token_hex(5)
    second_username = "ci_owner_race_" + suffix

    setup = SessionLocal()
    owner = setup.query(AdminUser).filter_by(username=owner_username).one()
    owner_id = owner.id
    owner_role = setup.query(Role).filter_by(code="owner").one()
    second_owner = AdminUser(
        username=second_username,
        display_name="CI Concurrent Owner",
        password_hash="unused-test-hash",
        is_active=True,
        roles=[owner_role],
    )
    setup.add(second_owner)
    setup.commit()
    second_owner_id = second_owner.id
    setup.close()

    first_reached_audit = Event()
    release_first = Event()
    second_started = Event()
    second_finished = Event()
    worker_context = local()
    original_record_audit = admins_api.record_audit

    def pause_first_before_commit(db, actor, *args, **kwargs):
        if getattr(worker_context, "pause_before_commit", False):
            first_reached_audit.set()
            if not release_first.wait(timeout=10):
                raise TimeoutError("test did not release the first owner transaction")
        return original_record_audit(db, actor, *args, **kwargs)

    monkeypatch.setattr(admins_api, "record_audit", pause_first_before_commit)

    def demote(caller_id: int, target_id: int, *, pause_before_commit: bool, started=None, finished=None):
        db = SessionLocal()
        try:
            caller = (
                db.query(AdminUser)
                .options(selectinload(AdminUser.roles))
                .filter(AdminUser.id == caller_id)
                .one()
            )
            worker_context.pause_before_commit = pause_before_commit
            if started is not None:
                started.set()
            try:
                return admins_api.update_admin(
                    target_id,
                    AdminUserUpdate(role_codes=["viewer"]),
                    db,
                    caller,
                )
            except HTTPException as exc:
                return exc.status_code
        finally:
            db.close()
            if finished is not None:
                finished.set()

    second_future = None
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first_future = pool.submit(
                demote,
                owner_id,
                second_owner_id,
                pause_before_commit=True,
            )
            assert first_reached_audit.wait(timeout=5), "first transaction did not reach its pre-commit hold"

            second_future = pool.submit(
                demote,
                second_owner_id,
                owner_id,
                pause_before_commit=False,
                started=second_started,
                finished=second_finished,
            )
            assert second_started.wait(timeout=5), "second owner request did not start"

            # The first transaction still owns the shared owner-role row lock.
            # A second demotion must not pass its fresh owner check until the
            # first transaction commits and removes the caller's owner role.
            assert not second_finished.wait(timeout=1), "second owner update bypassed the owner-role lock"
            release_first.set()

            first_result = first_future.result(timeout=10)
            second_result = second_future.result(timeout=10)

        assert getattr(first_result, "id", None) == second_owner_id
        assert second_result == 403

        verify = SessionLocal()
        remaining_owner_ids = {
            row[0]
            for row in (
                verify.query(AdminUser.id)
                .join(AdminUser.roles)
                .filter(AdminUser.is_active.is_(True), Role.code == "owner")
                .all()
            )
        }
        verify.close()
        assert remaining_owner_ids == {owner_id}
    finally:
        release_first.set()
        cleanup = SessionLocal()
        account = cleanup.query(AdminUser).filter_by(username=second_username).first()
        if account is not None:
            account.roles = []
            cleanup.delete(account)
        cleanup.commit()
        cleanup.close()


def test_manager_credentials_are_opt_in_and_response_schemas_hide_secrets():
    db = SessionLocal()
    try:
        manager = db.query(Role).filter_by(code="manager").one()
        manager_user = AdminUser(roles=[manager])
        assert not has_permission(manager_user, "cards.credentials")
        assert not has_permission(manager_user, "printing.credentials")
    finally:
        db.close()

    assert "password" not in AdminUserResponse.model_fields
    assert "password_hash" not in AdminUserResponse.model_fields
    assert {
        "api_secret",
        "radius_secret",
        "api_secret_encrypted",
        "radius_secret_encrypted",
    }.isdisjoint(RouterResponse.model_fields)
