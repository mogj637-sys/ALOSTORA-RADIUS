import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.db.session import SessionLocal
from app.models.auth import AdminUser, Role
from app.models.core import RadiusSession, Router


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
            "username": f"{label}{secrets.token_hex(5).upper()}",
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
            "idempotency_key": f"scope-print-{secrets.token_hex(8)}",
            "point_of_sale_id": point_id,
            "card_ids": [card["id"]],
        },
    )
    assert printed.status_code == 201, printed.text
    return card


def test_employee_can_search_any_pos_card_but_cannot_browse_all_cards_or_pos_finances(owner_client):
    client, owner_headers, _ = owner_client
    point_a = _create_point(client, owner_headers, "SCOPEA")
    point_b = _create_point(client, owner_headers, "SCOPEB")
    card_a = _create_card(client, owner_headers, point_a["id"], "CARD_A")
    card_b = _create_card(client, owner_headers, point_b["id"], "CARD_B")

    # Seed one active and one historical session for a card belonging to POS B.
    db = SessionLocal()
    now = datetime.now(timezone.utc)
    router = Router(
        name="CI employee session router",
        nas_identifier="ci-employee-session-" + secrets.token_hex(4),
        management_host="127.0.0.1",
        radius_secret_encrypted="test-encrypted-secret",
        is_active=True,
    )
    db.add(router)
    db.flush()
    db.add_all([
        RadiusSession(
            card_id=UUID(card_b["id"]),
            router_id=router.id,
            acct_session_id="active-" + secrets.token_hex(4),
            framed_ip_address="10.10.0.10",
            calling_station_id="AA:BB:CC:DD:EE:01",
            started_at=now - timedelta(minutes=30),
            last_update_at=now,
            session_time_seconds=1800,
            input_octets=1024,
            output_octets=2048,
        ),
        RadiusSession(
            card_id=UUID(card_b["id"]),
            router_id=router.id,
            acct_session_id="stopped-" + secrets.token_hex(4),
            framed_ip_address="10.10.0.11",
            calling_station_id="AA:BB:CC:DD:EE:02",
            started_at=now - timedelta(hours=2),
            last_update_at=now - timedelta(hours=1),
            stopped_at=now - timedelta(hours=1),
            session_time_seconds=3600,
            input_octets=4096,
            output_octets=8192,
        ),
    ])
    db.commit()
    active_session_id = (
        db.query(RadiusSession.id)
        .filter(RadiusSession.card_id == UUID(card_b["id"]), RadiusSession.stopped_at.is_(None))
        .scalar()
    )
    db.close()

    role_code = "ci_card_search_" + secrets.token_hex(4)
    staff_username = "ci_search_staff_" + secrets.token_hex(4)
    staff_id = None

    try:
        role = client.post(
            "/api/v1/admins/roles",
            headers=owner_headers,
            json={"code": role_code, "name": "موظف بحث الكروت"},
        )
        assert role.status_code == 201, role.text

        permissions = client.put(
            f"/api/v1/admins/roles/{role_code}/permissions",
            headers=owner_headers,
            json={"permission_codes": ["cards.view", "sessions.view", "pos.view"]},
        )
        assert permissions.status_code == 200, permissions.text

        staff = client.post(
            "/api/v1/admins",
            headers=owner_headers,
            json={
                "username": staff_username,
                "display_name": "موظف بحث",
                "password": "ci-search-staff-password-123",
                "role_codes": [role_code],
                "point_of_sale_ids": [point_a["id"]],
            },
        )
        assert staff.status_code == 201, staff.text
        staff_id = staff.json()["id"]

        login = client.post(
            "/api/v1/auth/login",
            json={
                "username": staff_username,
                "password": "ci-search-staff-password-123",
            },
        )
        assert login.status_code == 200, login.text
        staff_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        # A normal employee must search for a card; the search is global,
        # regardless of the point of sale to which that card is allocated.
        browse = client.get("/api/v1/cards", headers=staff_headers)
        assert browse.status_code == 403, browse.text

        by_username = client.get(
            f"/api/v1/cards?search={card_b['username']}",
            headers=staff_headers,
        )
        assert by_username.status_code == 200, by_username.text
        assert [item["id"] for item in by_username.json()] == [card_b["id"]]

        by_serial = client.get(
            f"/api/v1/cards?search={card_b['serial_number']}",
            headers=staff_headers,
        )
        assert by_serial.status_code == 200, by_serial.text
        assert [item["id"] for item in by_serial.json()] == [card_b["id"]]

        # Once a card is found, the employee can inspect its complete session
        # history, including sessions created through another point of sale.
        history = client.get(
            f"/api/v1/cards/{card_b['id']}/sessions?search={card_b['username']}",
            headers=staff_headers,
        )
        assert history.status_code == 200, history.text
        assert history.json()["total_sessions"] == 2
        assert history.json()["active_sessions"] == 1
        assert len(history.json()["items"]) == 2
        assert {item["router_name"] for item in history.json()["items"]} == {
            "CI employee session router"
        }
        mismatched_search = client.get(
            f"/api/v1/cards/{card_b['id']}/sessions?search={card_a['username']}",
            headers=staff_headers,
        )
        assert mismatched_search.status_code == 404

        # Reading a card's sessions does not grant permission to disconnect it.
        disconnect = client.post(
            f"/api/v1/cards/sessions/{active_session_id}/disconnect",
            headers=staff_headers,
        )
        assert disconnect.status_code == 403

        # The owner retains the unrestricted card list.
        owner_cards = client.get("/api/v1/cards", headers=owner_headers)
        assert owner_cards.status_code == 200, owner_cards.text
        owner_ids = {item["id"] for item in owner_cards.json()}
        assert card_a["id"] in owner_ids
        assert card_b["id"] in owner_ids

        # Card-search permission does not grant access to another POS's
        # inventory or to any POS financial account.
        foreign_inventory = client.get(
            f"/api/v1/points-of-sale/{point_b['id']}/inventory",
            headers=staff_headers,
        )
        assert foreign_inventory.status_code == 403

        own_finances = client.get(
            f"/api/v1/points-of-sale/{point_a['id']}/account",
            headers=staff_headers,
        )
        assert own_finances.status_code == 403

        cannot_change_pos_controls = client.patch(
            f"/api/v1/points-of-sale/{point_a['id']}",
            headers=staff_headers,
            json={"debt_limit": "100.00", "allow_printing": False},
        )
        assert cannot_change_pos_controls.status_code == 403

    finally:
        db = SessionLocal()
        user = db.query(AdminUser).filter_by(username=staff_username).first()
        if user is not None:
            user.roles = []
            user.point_of_sales = []
            db.delete(user)
        role = db.query(Role).filter_by(code=role_code).first()
        if role is not None:
            db.delete(role)
        db.commit()
        db.close()
