import secrets

from app.db.session import SessionLocal
from app.models.auth import AdminUser, Role
from app.models.core import CardTemplate, Plan


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
