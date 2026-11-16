import secrets

from app.db.session import SessionLocal
from app.models.auth import AdminUser, Role


def _create_point(client, headers, label):
    response = client.post(
        "/api/v1/points-of-sale",
        headers=headers,
        json={
            "code": f"{label}-{secrets.token_hex(4).upper()}",
            "name": f"نقطة {label}",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_card(client, headers, point_id, label):
    plan = client.post(
        "/api/v1/plans",
        headers=headers,
        json={
            "code": f"{label}-{secrets.token_hex(4).upper()}",
            "name": f"باقة {label}",
            "price": "15.00",
        },
    )
    assert plan.status_code == 201, plan.text
    created = client.post(
        "/api/v1/cards/single",
        headers=headers,
        json={
            "plan_id": plan.json()["id"],
            "username": f"{label[:20]}{secrets.token_hex(5).upper()}",
            "card_type": "username_only",
            "point_of_sale_id": point_id,
        },
    )
    assert created.status_code == 201, created.text
    card = created.json()
    printed = client.post(
        "/api/v1/print-jobs",
        headers=headers,
        json={
            "idempotency_key": f"individual-scope-{secrets.token_hex(8)}",
            "point_of_sale_id": point_id,
            "card_ids": [card["id"]],
        },
    )
    assert printed.status_code == 201, printed.text
    return card


def _new_unprinted_card(client, headers, point_id, label):
    plan = client.post(
        "/api/v1/plans",
        headers=headers,
        json={
            "code": f"{label}-{secrets.token_hex(4).upper()}",
            "name": f"باقة {label}",
            "price": "20.00",
        },
    )
    assert plan.status_code == 201, plan.text
    response = client.post(
        "/api/v1/cards/single",
        headers=headers,
        json={
            "plan_id": plan.json()["id"],
            "username": f"{label[:20]}{secrets.token_hex(5).upper()}",
            "card_type": "username_only",
            "point_of_sale_id": point_id,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_employee_card_visibility_and_direct_permission_overrides(owner_client):
    client, owner_headers, _ = owner_client
    point_a = _create_point(client, owner_headers, "INDIVIDUALA")
    point_b = _create_point(client, owner_headers, "INDIVIDUALB")
    card_a = _create_card(client, owner_headers, point_a["id"], "INDIVIDUAL_CARD_A")
    card_b = _create_card(client, owner_headers, point_b["id"], "INDIVIDUAL_CARD_B")
    unprinted_batch_card = _new_unprinted_card(client, owner_headers, point_a["id"], "UNPRINTED_SCOPE")

    role_code = "ci_individual_" + secrets.token_hex(4)
    username = "ci_individual_staff_" + secrets.token_hex(4)
    staff_id = None
    try:
        role = client.post(
            "/api/v1/admins/roles",
            headers=owner_headers,
            json={"code": role_code, "name": "موظف بصلاحيات فردية"},
        )
        assert role.status_code == 201, role.text
        role_permissions = client.put(
            f"/api/v1/admins/roles/{role_code}/permissions",
            headers=owner_headers,
            json={"permission_codes": ["cards.view", "pos.view"]},
        )
        assert role_permissions.status_code == 200, role_permissions.text

        staff = client.post(
            "/api/v1/admins",
            headers=owner_headers,
            json={
                "username": username,
                "display_name": "موظف بصلاحيات فردية",
                "password": "ci-individual-staff-password-123",
                "role_codes": [role_code],
                "point_of_sale_ids": [point_a["id"]],
                "card_visibility": "search_any",
            },
        )
        assert staff.status_code == 201, staff.text
        staff_id = staff.json()["id"]

        login = client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": "ci-individual-staff-password-123"},
        )
        assert login.status_code == 200, login.text
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        identity = client.get("/api/v1/auth/me", headers=headers)
        assert identity.status_code == 200
        assert identity.json()["card_visibility"] == "search_any"
        assert "printing.manage" not in identity.json()["permissions"]

        assert client.get("/api/v1/cards", headers=headers).status_code == 403
        found_b = client.get(f"/api/v1/cards?search={card_b['username']}", headers=headers)
        assert found_b.status_code == 200
        assert [item["id"] for item in found_b.json()] == [card_b["id"]]

        assigned = client.patch(
            f"/api/v1/admins/{staff_id}",
            headers=owner_headers,
            json={"card_visibility": "assigned"},
        )
        assert assigned.status_code == 200, assigned.text
        assigned_cards = client.get("/api/v1/cards", headers=headers)
        assert assigned_cards.status_code == 200, assigned_cards.text
        assigned_ids = {item["id"] for item in assigned_cards.json()}
        assert card_a["id"] in assigned_ids
        assert unprinted_batch_card["id"] in assigned_ids
        assert card_b["id"] not in assigned_ids
        assert client.get(f"/api/v1/cards?search={card_b['username']}", headers=headers).json() == []

        all_cards = client.patch(
            f"/api/v1/admins/{staff_id}",
            headers=owner_headers,
            json={"card_visibility": "all"},
        )
        assert all_cards.status_code == 200, all_cards.text
        all_result = client.get("/api/v1/cards", headers=headers)
        assert all_result.status_code == 200, all_result.text
        all_ids = {item["id"] for item in all_result.json()}
        assert card_a["id"] in all_ids
        assert unprinted_batch_card["id"] in all_ids
        assert card_b["id"] in all_ids
        # Global card visibility does not grant foreign POS inventory or finance access.
        assert client.get(f"/api/v1/points-of-sale/{point_b['id']}/inventory", headers=headers).status_code == 403
        assert client.get(f"/api/v1/points-of-sale/{point_b['id']}/account", headers=headers).status_code == 403

        denied_view = client.patch(
            f"/api/v1/admins/{staff_id}",
            headers=owner_headers,
            json={"permission_overrides": [{"permission_code": "cards.view", "allowed": False}]},
        )
        assert denied_view.status_code == 200, denied_view.text
        assert client.get("/api/v1/cards", headers=headers).status_code == 403

        restored_view_and_print = client.patch(
            f"/api/v1/admins/{staff_id}",
            headers=owner_headers,
            json={
                "permission_overrides": [
                    {"permission_code": "cards.view", "allowed": True},
                    {"permission_code": "printing.manage", "allowed": True},
                ]
            },
        )
        assert restored_view_and_print.status_code == 200, restored_view_and_print.text
        identity = client.get("/api/v1/auth/me", headers=headers)
        assert "printing.manage" in identity.json()["permissions"]

        imported = client.post(
            "/api/v1/cards/print-selection/resolve",
            headers=headers,
            json={
                "point_of_sale_id": point_a["id"],
                "identifiers": [unprinted_batch_card["username"], card_b["username"]],
            },
        )
        assert imported.status_code == 200, imported.text
        assert [item["id"] for item in imported.json()["items"]] == [unprinted_batch_card["id"]]
        assert imported.json()["unmatched"] == [card_b["username"]]

        printable = _new_unprinted_card(client, owner_headers, point_a["id"], "INDIVIDUAL_PRINT_ALLOWED")
        printed = client.post(
            "/api/v1/print-jobs",
            headers=headers,
            json={
                "idempotency_key": "individual-print-" + secrets.token_hex(8),
                "point_of_sale_id": point_a["id"],
                "card_ids": [printable["id"]],
            },
        )
        assert printed.status_code == 201, printed.text

        denied_print = client.patch(
            f"/api/v1/admins/{staff_id}",
            headers=owner_headers,
            json={
                "permission_overrides": [
                    {"permission_code": "cards.view", "allowed": True},
                    {"permission_code": "printing.manage", "allowed": False},
                ]
            },
        )
        assert denied_print.status_code == 200, denied_print.text
        another_printable = _new_unprinted_card(client, owner_headers, point_a["id"], "INDIVIDUAL_PRINT_DENIED")
        blocked_print = client.post(
            "/api/v1/print-jobs",
            headers=headers,
            json={
                "idempotency_key": "individual-print-denied-" + secrets.token_hex(8),
                "point_of_sale_id": point_a["id"],
                "card_ids": [another_printable["id"]],
            },
        )
        assert blocked_print.status_code == 403

    finally:
        db = SessionLocal()
        staff_user = db.query(AdminUser).filter_by(username=username).first()
        if staff_user is not None:
            staff_user.roles = []
            staff_user.point_of_sales = []
            db.delete(staff_user)
        role = db.query(Role).filter_by(code=role_code).first()
        if role is not None:
            db.delete(role)
        db.commit()
        db.close()
