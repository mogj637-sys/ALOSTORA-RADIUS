import secrets

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.models.auth import AdminUser, Role
from app.models.core import Card, CardEvent
from app.security import hash_password
from app.services.credentials import decrypt_credential


@pytest.fixture
def owner_client(monkeypatch):
    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY", Fernet.generate_key().decode("ascii"))
    username = "ci_owner_" + secrets.token_hex(4)
    password = "a-strong-ci-password-123"

    db = SessionLocal()
    role = db.query(Role).filter_by(code="owner").first()
    if role is None:
        role = Role(code="owner", name="System Owner")
        db.add(role)
        db.flush()

    user = AdminUser(
        username=username,
        display_name="CI Owner",
        password_hash=hash_password(password),
        is_active=True,
        roles=[role],
    )
    db.add(user)
    db.commit()
    user_id = user.id
    db.close()

    with TestClient(app) as client:
        login = client.post("/api/v1/auth/login", json={"username": username, "password": password})
        assert login.status_code == 200
        token = login.json()["access_token"]
        yield client, {"Authorization": f"Bearer {token}"}, username

    cleanup = SessionLocal()
    account = cleanup.get(AdminUser, user_id)
    if account is not None:
        account.roles = []
        cleanup.delete(account)
        cleanup.commit()
    cleanup.close()


def test_owner_can_create_plan_and_generate_batch(owner_client):
    client, headers, actor = owner_client
    code = "CI-" + secrets.token_hex(4).upper()

    plan_response = client.post(
        "/api/v1/plans",
        headers=headers,
        json={
            "code": code,
            "name": "CI test plan",
            "price": "12.50",
            "data_limit_bytes": 1048576,
            "session_time_limit_seconds": 3600,
            "validity_period_seconds": 86400,
            "speed_profile": "test-speed",
        },
    )
    assert plan_response.status_code == 201, plan_response.text
    plan_id = plan_response.json()["id"]

    batch_response = client.post(
        "/api/v1/cards/batch",
        headers=headers,
        json={
            "plan_id": plan_id,
            "quantity": 5,
            "card_type": "separate_credentials",
            "generation_mode": "digits",
            "username_length": 8,
            "password_length": 10,
            "prefix": "77",
        },
    )
    assert batch_response.status_code == 201, batch_response.text
    payload = batch_response.json()
    assert payload["created_count"] == 5
    assert all(item["username"].startswith("77") for item in payload["cards"])
    assert all(len(item["password"]) == 10 for item in payload["cards"])

    db = SessionLocal()
    usernames = [item["username"] for item in payload["cards"]]
    saved = db.query(Card).filter(Card.username.in_(usernames)).all()
    assert len(saved) == 5
    assert all(decrypt_credential(card.credential_ciphertext) for card in saved)
    assert all(card.status == "generated" for card in saved)
    assert all(card.first_used_at is None and card.expires_at is None for card in saved)
    events = db.query(CardEvent).filter(CardEvent.card_id.in_([card.id for card in saved])).all()
    assert len(events) == 5
    assert all(event.actor == actor for event in events)
    db.close()


def test_single_free_card_is_created_outside_commercial_value(owner_client):
    client, headers, _ = owner_client
    code = "FREE-" + secrets.token_hex(4).upper()
    plan_response = client.post(
        "/api/v1/plans",
        headers=headers,
        json={"code": code, "name": "Free test plan", "price": "50.00"},
    )
    assert plan_response.status_code == 201, plan_response.text

    username = "FREE" + secrets.token_hex(4).upper()
    response = client.post(
        "/api/v1/cards/single",
        headers=headers,
        json={
            "plan_id": plan_response.json()["id"],
            "username": username,
            "card_type": "username_only",
            "is_free": True,
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["password"] == ""
    assert response.json()["is_free"] is True

    db = SessionLocal()
    card = db.query(Card).filter_by(username=username).one()
    assert card.price_snapshot == 0
    assert decrypt_credential(card.credential_ciphertext) == ""
    db.close()


def test_card_management_requires_owner_authentication(owner_client):
    client, _, _ = owner_client
    response = client.get("/api/v1/cards")
    assert response.status_code == 401


def test_plan_can_be_updated_and_deactivated(owner_client):
    client, headers, _ = owner_client
    code = "EDIT-" + secrets.token_hex(4).upper()
    created = client.post(
        "/api/v1/plans",
        headers=headers,
        json={"code": code, "name": "Editable plan", "price": "10.00"},
    )
    assert created.status_code == 201, created.text
    plan_id = created.json()["id"]

    updated = client.patch(
        f"/api/v1/plans/{plan_id}",
        headers=headers,
        json={"name": "Updated plan", "price": "15.50", "is_active": False},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == "Updated plan"
    assert updated.json()["price"] == "15.50"
    assert updated.json()["is_active"] is False

    active_list = client.get("/api/v1/plans", headers=headers)
    all_list = client.get("/api/v1/plans?include_inactive=true", headers=headers)
    assert all(item["id"] != plan_id for item in active_list.json())
    assert any(item["id"] == plan_id for item in all_list.json())


def test_card_search_and_audited_status_lifecycle(owner_client):
    client, headers, actor = owner_client
    code = "LIFE-" + secrets.token_hex(4).upper()
    plan = client.post(
        "/api/v1/plans",
        headers=headers,
        json={"code": code, "name": "Lifecycle plan", "price": "20.00"},
    )
    assert plan.status_code == 201, plan.text

    username = "LIFE" + secrets.token_hex(4).upper()
    created = client.post(
        "/api/v1/cards/single",
        headers=headers,
        json={
            "plan_id": plan.json()["id"],
            "username": username,
            "card_type": "username_only",
        },
    )
    assert created.status_code == 201, created.text
    card_id = created.json()["id"]
    serial = created.json()["serial_number"]

    searched = client.get(f"/api/v1/cards?search={username}", headers=headers)
    assert searched.status_code == 200
    assert len(searched.json()) == 1
    assert searched.json()[0]["username"] == username

    suspended = client.patch(
        f"/api/v1/cards/{card_id}/status",
        headers=headers,
        json={"action": "suspend"},
    )
    assert suspended.status_code == 200, suspended.text
    assert suspended.json()["status"] == "suspended"

    repeated_suspend = client.patch(
        f"/api/v1/cards/{card_id}/status",
        headers=headers,
        json={"action": "suspend"},
    )
    assert repeated_suspend.status_code == 409

    restored = client.patch(
        f"/api/v1/cards/{card_id}/status",
        headers=headers,
        json={"action": "reactivate"},
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["status"] == "generated"

    cancelled = client.patch(
        f"/api/v1/cards/{card_id}/status",
        headers=headers,
        json={"action": "cancel"},
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"

    cannot_reactivate = client.patch(
        f"/api/v1/cards/{card_id}/status",
        headers=headers,
        json={"action": "reactivate"},
    )
    assert cannot_reactivate.status_code == 409

    db = SessionLocal()
    events = (
        db.query(CardEvent)
        .filter(CardEvent.card_id == UUID(card_id))
        .order_by(CardEvent.created_at.asc(), CardEvent.id.asc())
        .all()
    )
    assert [event.event_type for event in events] == [
        "created", "suspended", "reactivated", "cancelled"
    ]
    assert all(event.actor == actor for event in events)
    db.close()
