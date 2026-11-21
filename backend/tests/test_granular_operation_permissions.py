import secrets
from uuid import uuid4

from app.db.session import SessionLocal
from app.models.auth import AdminUser, Role
from app.models.core import CardTemplate, Plan, PointOfSale, Router
from app.models.user_manager import UserManagerSyncRun


def _create_role_user(client, owner_headers, permissions, *, point_ids=None):
    role_code = "ci_permissions_" + secrets.token_hex(4)
    username = "ci_permissions_" + secrets.token_hex(4)
    password = "ci-permissions-user-password-123"
    role = client.post(
        "/api/v1/admins/roles",
        headers=owner_headers,
        json={"code": role_code, "name": "CI صلاحيات تفصيلية"},
    )
    assert role.status_code == 201, role.text
    granted = client.put(
        f"/api/v1/admins/roles/{role_code}/permissions",
        headers=owner_headers,
        json={"permission_codes": permissions},
    )
    assert granted.status_code == 200, granted.text
    created = client.post(
        "/api/v1/admins",
        headers=owner_headers,
        json={
            "username": username,
            "display_name": "CI صلاحيات تفصيلية",
            "password": password,
            "role_codes": [role_code],
            "point_of_sale_ids": point_ids or [],
        },
    )
    assert created.status_code == 201, created.text
    login = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert login.status_code == 200, login.text
    return role_code, username, created.json()["id"], {
        "Authorization": f"Bearer {login.json()['access_token']}"
    }


def _cleanup_role_user(role_code, username):
    db = SessionLocal()
    user = db.query(AdminUser).filter_by(username=username).first()
    if user is not None:
        user.roles = []
        user.point_of_sales = []
        db.delete(user)
    role = db.query(Role).filter_by(code=role_code).first()
    if role is not None:
        role.permissions = []
        db.delete(role)
    db.commit()
    db.close()


def test_print_history_uses_printing_view_and_enforces_point_scope(owner_client):
    client, owner_headers, _ = owner_client
    point_a = client.post(
        "/api/v1/points-of-sale",
        headers=owner_headers,
        json={"code": "CI-PRINT-A-" + secrets.token_hex(3), "name": "CI نقطة الطباعة أ"},
    )
    point_b = client.post(
        "/api/v1/points-of-sale",
        headers=owner_headers,
        json={"code": "CI-PRINT-B-" + secrets.token_hex(3), "name": "CI نقطة الطباعة ب"},
    )
    assert point_a.status_code == 201, point_a.text
    assert point_b.status_code == 201, point_b.text
    plan = client.post(
        "/api/v1/plans",
        headers=owner_headers,
        json={
            "code": "CI-PRINT-PLAN-" + secrets.token_hex(3),
            "name": "CI باقة الطباعة",
            "price": "10.00",
        },
    )
    assert plan.status_code == 201, plan.text
    card = client.post(
        "/api/v1/cards/single",
        headers=owner_headers,
        json={
            "plan_id": plan.json()["id"],
            "username": "CI_PRINT_" + secrets.token_hex(5),
            "card_type": "username_only",
            "point_of_sale_id": point_a.json()["id"],
        },
    )
    assert card.status_code == 201, card.text
    printed = client.post(
        "/api/v1/print-jobs",
        headers=owner_headers,
        json={
            "idempotency_key": "ci-print-history-" + secrets.token_hex(6),
            "point_of_sale_id": point_a.json()["id"],
            "card_ids": [card.json()["id"]],
        },
    )
    assert printed.status_code == 201, printed.text

    role_code, username, _, staff_headers = _create_role_user(
        client, owner_headers, ["printing.view"], point_ids=[point_a.json()["id"]]
    )
    try:
        identity = client.get("/api/v1/auth/me", headers=staff_headers)
        assert identity.status_code == 200
        assert identity.json()["permissions"] == ["printing.view"]
        assert client.get("/api/v1/points-of-sale", headers=staff_headers).status_code == 403

        history = client.get(
            f"/api/v1/print-jobs?point_of_sale_id={point_a.json()['id']}",
            headers=staff_headers,
        )
        assert history.status_code == 200, history.text
        assert len(history.json()) == 1
        assert "password" not in history.json()[0]["cards"][0]

        outside_scope = client.get(
            f"/api/v1/print-jobs?point_of_sale_id={point_b.json()['id']}",
            headers=staff_headers,
        )
        assert outside_scope.status_code == 403
    finally:
        _cleanup_role_user(role_code, username)


def test_plan_delete_is_independent_and_blocks_active_or_referenced_plans(owner_client):
    client, owner_headers, _ = owner_client
    plan = client.post(
        "/api/v1/plans",
        headers=owner_headers,
        json={
            "code": "CI-DELETE-PLAN-" + secrets.token_hex(3),
            "name": "CI باقة الحذف",
            "price": "12.00",
        },
    )
    assert plan.status_code == 201, plan.text
    plan_id = plan.json()["id"]
    template_code = "ci-plan-reference-" + secrets.token_hex(4)

    viewer_role, viewer_name, _, viewer_headers = _create_role_user(
        client, owner_headers, ["plans.view"]
    )
    delete_role, delete_name, _, delete_headers = _create_role_user(
        client, owner_headers, ["plans.delete"]
    )
    try:
        assert client.get("/api/v1/plans?include_inactive=true", headers=viewer_headers).status_code == 200
        assert client.delete(f"/api/v1/plans/{plan_id}", headers=viewer_headers).status_code == 403
        assert client.get("/api/v1/plans?include_inactive=true", headers=delete_headers).status_code == 403
        assert client.delete(f"/api/v1/plans/{plan_id}", headers=delete_headers).status_code == 409

        deactivated = client.patch(
            f"/api/v1/plans/{plan_id}",
            headers=owner_headers,
            json={"is_active": False},
        )
        assert deactivated.status_code == 200, deactivated.text

        db = SessionLocal()
        db.add(CardTemplate(code=template_code, name="CI قالب مرتبط", plan_id=plan_id))
        db.commit()
        db.close()

        referenced = client.delete(f"/api/v1/plans/{plan_id}", headers=delete_headers)
        assert referenced.status_code == 409, referenced.text

        db = SessionLocal()
        template = db.query(CardTemplate).filter_by(code=template_code).first()
        if template is not None:
            db.delete(template)
            db.commit()
        db.close()

        deleted = client.delete(f"/api/v1/plans/{plan_id}", headers=delete_headers)
        assert deleted.status_code == 204, deleted.text
        remaining = client.get("/api/v1/plans?include_inactive=true", headers=owner_headers)
        assert all(item["id"] != plan_id for item in remaining.json())
    finally:
        db = SessionLocal()
        template = db.query(CardTemplate).filter_by(code=template_code).first()
        if template is not None:
            db.delete(template)
        db.commit()
        db.close()
        _cleanup_role_user(viewer_role, viewer_name)
        _cleanup_role_user(delete_role, delete_name)


def test_owner_cannot_disable_or_demote_self_and_admin_responses_hide_password_hash(owner_client):
    client, owner_headers, username = owner_client
    admins = client.get("/api/v1/admins", headers=owner_headers)
    assert admins.status_code == 200, admins.text
    owner = next(item for item in admins.json() if item["username"] == username)
    assert "password_hash" not in owner
    assert "password" not in owner

    disabled = client.patch(
        f"/api/v1/admins/{owner['id']}",
        headers=owner_headers,
        json={"is_active": False},
    )
    assert disabled.status_code == 400

    demoted = client.patch(
        f"/api/v1/admins/{owner['id']}",
        headers=owner_headers,
        json={"role_codes": ["manager"]},
    )
    assert demoted.status_code == 400

    identity = client.get("/api/v1/auth/me", headers=owner_headers)
    assert identity.status_code == 200
    assert "password_hash" not in identity.json()
    assert "password" not in identity.json()


def test_router_delete_is_independent_and_preserves_active_or_referenced_routers(owner_client):
    client, owner_headers, _ = owner_client
    nas_identifier = "CI-ROUTER-DELETE-" + secrets.token_hex(4)
    created = client.post(
        "/api/v1/routers",
        headers=owner_headers,
        json={
            "name": "CI Router Delete",
            "nas_identifier": nas_identifier,
            "management_host": "192.0.2.77",
            "radius_secret": "ci-router-radius-secret-" + secrets.token_hex(6),
        },
    )
    assert created.status_code == 201, created.text
    router_id = created.json()["id"]

    viewer_role, viewer_name, _, viewer_headers = _create_role_user(
        client, owner_headers, ["routers.view"]
    )
    delete_role, delete_name, _, delete_headers = _create_role_user(
        client, owner_headers, ["routers.delete"]
    )
    sync_run_id = uuid4()
    try:
        assert client.get("/api/v1/routers", headers=viewer_headers).status_code == 200
        assert client.delete(f"/api/v1/routers/{router_id}", headers=viewer_headers).status_code == 403
        assert client.get("/api/v1/routers", headers=delete_headers).status_code == 403

        active_delete = client.delete(f"/api/v1/routers/{router_id}", headers=delete_headers)
        assert active_delete.status_code == 409, active_delete.text

        deactivated = client.patch(
            f"/api/v1/routers/{router_id}",
            headers=owner_headers,
            json={"is_active": False},
        )
        assert deactivated.status_code == 200, deactivated.text

        db = SessionLocal()
        db.add(
            UserManagerSyncRun(
                id=sync_run_id,
                router_id=router_id,
                run_type="preview",
                status="completed",
            )
        )
        db.commit()
        db.close()

        referenced_delete = client.delete(f"/api/v1/routers/{router_id}", headers=delete_headers)
        assert referenced_delete.status_code == 409, referenced_delete.text

        db = SessionLocal()
        assert db.get(UserManagerSyncRun, sync_run_id) is not None
        assert db.get(Router, router_id) is not None
        db.query(UserManagerSyncRun).filter(UserManagerSyncRun.id == sync_run_id).delete()
        db.commit()
        db.close()

        deleted = client.delete(f"/api/v1/routers/{router_id}", headers=delete_headers)
        assert deleted.status_code == 204, deleted.text

        db = SessionLocal()
        assert db.get(Router, router_id) is None
        db.close()
    finally:
        db = SessionLocal()
        db.query(UserManagerSyncRun).filter(UserManagerSyncRun.id == sync_run_id).delete()
        db.commit()
        db.close()
        remaining = client.get("/api/v1/routers?include_inactive=true", headers=owner_headers)
        if any(item["id"] == router_id for item in remaining.json()):
            client.patch(
                f"/api/v1/routers/{router_id}",
                headers=owner_headers,
                json={"is_active": False},
            )
            client.delete(f"/api/v1/routers/{router_id}", headers=owner_headers)
        _cleanup_role_user(viewer_role, viewer_name)
        _cleanup_role_user(delete_role, delete_name)


def test_stale_owner_request_is_rejected_after_concurrent_demotion(owner_client):
    _, _, _ = owner_client
    from fastapi import HTTPException

    from app.api.admins import create_admin, create_role, update_admin, update_role_permissions
    from app.api.deps import get_current_owner
    from app.models.auth import user_roles
    from app.schemas.admins import AdminRoleCreate, AdminUserCreate, AdminUserUpdate

    suffix = secrets.token_hex(5)
    caller_name = "ci_stale_owner_" + suffix
    target_name = "ci_target_owner_" + suffix

    db = SessionLocal()
    owner_role = db.query(Role).filter_by(code="owner").one()
    caller = AdminUser(
        username=caller_name,
        display_name="CI Stale Owner",
        password_hash="unused-test-hash",
        is_active=True,
        roles=[owner_role],
    )
    target = AdminUser(
        username=target_name,
        display_name="CI Target Owner",
        password_hash="unused-test-hash",
        is_active=True,
        roles=[owner_role],
    )
    db.add_all([caller, target])
    db.commit()
    caller_id, target_id = caller.id, target.id

    # Keep the caller's role collection loaded in this session, then simulate
    # another committed request demoting that account before this request runs.
    caller = db.get(AdminUser, caller_id)
    assert any(role.code == "owner" for role in caller.roles)
    concurrent = SessionLocal()
    concurrent.execute(
        user_roles.delete().where(
            user_roles.c.user_id == caller_id,
            user_roles.c.role_id == owner_role.id,
        )
    )
    concurrent.commit()
    concurrent.close()

    try:
        try:
            get_current_owner(caller, db)
            raise AssertionError("A demoted owner must be rejected by the owner dependency")
        except HTTPException as exc:
            assert exc.status_code == 403

        try:
            update_admin(
                target_id,
                AdminUserUpdate(role_codes=["manager"]),
                db,
                caller,
            )
            raise AssertionError("A stale owner request must be rejected")
        except HTTPException as exc:
            assert exc.status_code == 403

        # The same stale owner object must not authorize other privileged writes.
        stale_admin = AdminUserCreate(
            username="ci_stale_created_" + suffix,
            display_name="CI Stale Created",
            password="ci-stale-created-password-123",
            role_codes=["manager"],
        )
        stale_role = AdminRoleCreate(
            code="ci_stale_role_" + suffix,
            name="CI Stale Role",
        )
        for operation in (
            lambda: create_admin(stale_admin, db, caller),
            lambda: create_role(stale_role, db, caller),
            lambda: update_role_permissions("manager", ["cards.view"], db, caller),
        ):
            try:
                operation()
                raise AssertionError("A stale owner request must not mutate administrator access")
            except HTTPException as exc:
                assert exc.status_code == 403

        db.rollback()
        assert any(role.code == "owner" for role in db.get(AdminUser, target_id).roles)
    finally:
        db.rollback()
        db.close()
        cleanup = SessionLocal()
        for username in (caller_name, target_name):
            account = cleanup.query(AdminUser).filter_by(username=username).first()
            if account is not None:
                account.roles = []
                cleanup.delete(account)
        cleanup.commit()
        cleanup.close()



def test_point_of_sale_delete_is_scoped_and_preserves_other_admin_assignments(owner_client):
    client, owner_headers, _ = owner_client
    created = client.post(
        "/api/v1/points-of-sale",
        headers=owner_headers,
        json={"code": "CI-DELETE-POS-" + secrets.token_hex(4), "name": "CI نقطة حذف"},
    )
    outside = client.post(
        "/api/v1/points-of-sale",
        headers=owner_headers,
        json={"code": "CI-DELETE-OUT-" + secrets.token_hex(4), "name": "CI نقطة خارج النطاق"},
    )
    assert created.status_code == 201, created.text
    assert outside.status_code == 201, outside.text
    point_id = created.json()["id"]
    outside_id = outside.json()["id"]

    viewer_role, viewer_name, _, viewer_headers = _create_role_user(
        client, owner_headers, ["pos.view"], point_ids=[point_id]
    )
    delete_role, delete_name, _, delete_headers = _create_role_user(
        client, owner_headers, ["pos.delete"], point_ids=[point_id]
    )
    try:
        assert client.get("/api/v1/points-of-sale?include_inactive=true", headers=viewer_headers).status_code == 200
        assert client.delete(f"/api/v1/points-of-sale/{point_id}", headers=viewer_headers).status_code == 403
        assert client.get("/api/v1/points-of-sale?include_inactive=true", headers=delete_headers).status_code == 403
        assert client.delete(f"/api/v1/points-of-sale/{outside_id}", headers=delete_headers).status_code == 403

        active_delete = client.delete(f"/api/v1/points-of-sale/{point_id}", headers=delete_headers)
        assert active_delete.status_code == 409, active_delete.text

        stopped = client.patch(
            f"/api/v1/points-of-sale/{point_id}",
            headers=owner_headers,
            json={"is_active": False},
        )
        assert stopped.status_code == 200, stopped.text

        # Another employee assignment must keep the point from being deleted.
        assigned_delete = client.delete(f"/api/v1/points-of-sale/{point_id}", headers=delete_headers)
        assert assigned_delete.status_code == 409, assigned_delete.text
        assert "تخصيصات حسابات الإدارة" in assigned_delete.json()["detail"]

        db = SessionLocal()
        viewer = db.query(AdminUser).filter_by(username=viewer_name).one()
        viewer.point_of_sales = [item for item in viewer.point_of_sales if item.id != point_id]
        db.commit()
        db.close()

        # The caller's own assignment is part of the deleted point, not a foreign reference.
        deleted = client.delete(f"/api/v1/points-of-sale/{point_id}", headers=delete_headers)
        assert deleted.status_code == 204, deleted.text
        remaining = client.get("/api/v1/points-of-sale?include_inactive=true", headers=owner_headers)
        assert all(item["id"] != point_id for item in remaining.json())
    finally:
        _cleanup_role_user(viewer_role, viewer_name)
        _cleanup_role_user(delete_role, delete_name)
        for cleanup_point_id in (point_id, outside_id):
            db = SessionLocal()
            point = db.get(PointOfSale, cleanup_point_id)
            db.close()
            if point is not None:
                if point.is_active:
                    client.patch(
                        f"/api/v1/points-of-sale/{cleanup_point_id}",
                        headers=owner_headers,
                        json={"is_active": False},
                    )
                client.delete(f"/api/v1/points-of-sale/{cleanup_point_id}", headers=owner_headers)
