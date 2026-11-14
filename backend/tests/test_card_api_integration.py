import secrets
from uuid import UUID

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.models.auth import AdminUser, Role
from app.models.core import (
    Card,
    CardEvent,
    PointOfSale,
    PosInventoryMovement,
    PrintJob,
    PrintJobItem,
)
from app.security import hash_password
from app.services.credentials import decrypt_credential


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


def test_print_job_allocates_commercial_cards_once_and_reprint_is_free_of_movements(owner_client):
    client, headers, actor = owner_client
    code = "PRINT-" + secrets.token_hex(4).upper()
    plan = client.post(
        "/api/v1/plans",
        headers=headers,
        json={"code": code, "name": "Print test plan", "price": "25.00"},
    )
    assert plan.status_code == 201, plan.text

    commercial_username = "SALE" + secrets.token_hex(4).upper()
    commercial = client.post(
        "/api/v1/cards/single",
        headers=headers,
        json={
            "plan_id": plan.json()["id"],
            "username": commercial_username,
            "card_type": "username_only",
        },
    )
    assert commercial.status_code == 201, commercial.text

    free_username = "GIFT" + secrets.token_hex(4).upper()
    free = client.post(
        "/api/v1/cards/single",
        headers=headers,
        json={
            "plan_id": plan.json()["id"],
            "username": free_username,
            "card_type": "username_only",
            "is_free": True,
        },
    )
    assert free.status_code == 201, free.text

    db = SessionLocal()
    pos = PointOfSale(
        code="POS-" + secrets.token_hex(4).upper(),
        name="CI print point",
        is_active=True,
    )
    db.add(pos)
    db.commit()
    pos_id = pos.id
    db.close()

    card_ids = [commercial.json()["id"], free.json()["id"]]
    payload = {
        "idempotency_key": "print-" + secrets.token_hex(12),
        "point_of_sale_id": pos_id,
        "card_ids": card_ids,
        "template_code": "green-voucher",
    }
    first = client.post("/api/v1/print-jobs", headers=headers, json=payload)
    assert first.status_code == 201, first.text
    first_data = first.json()
    assert first_data["card_count"] == 2
    assert first_data["commercial_card_count"] == 1
    assert first_data["free_card_count"] == 1
    assert first_data["total_amount"] == "25.00"
    assert first_data["is_reprint"] is False

    repeated = client.post("/api/v1/print-jobs", headers=headers, json=payload)
    assert repeated.status_code == 201, repeated.text
    assert repeated.json()["id"] == first_data["id"]

    reprint_payload = {
        **payload,
        "idempotency_key": "reprint-" + secrets.token_hex(12),
        "is_reprint": True,
    }
    reprinted = client.post("/api/v1/print-jobs", headers=headers, json=reprint_payload)
    assert reprinted.status_code == 201, reprinted.text
    assert reprinted.json()["is_reprint"] is True
    assert reprinted.json()["total_amount"] == "0.00"

    db = SessionLocal()
    commercial_card = db.query(Card).filter_by(username=commercial_username).one()
    free_card = db.query(Card).filter_by(username=free_username).one()
    assert commercial_card.assigned_pos_id == pos_id
    assert commercial_card.status == "allocated"
    assert commercial_card.allocated_at is not None
    assert free_card.assigned_pos_id is None
    assert free_card.status == "generated"

    movements = db.query(PosInventoryMovement).filter_by(point_of_sale_id=pos_id).all()
    assert len(movements) == 1
    assert movements[0].card_id == UUID(commercial.json()["id"])
    assert movements[0].amount == 25

    jobs = db.query(PrintJob).filter(PrintJob.point_of_sale_id == pos_id).all()
    assert len(jobs) == 2
    items = db.query(PrintJobItem).filter(
        PrintJobItem.print_job_id.in_([job.id for job in jobs])
    ).all()
    assert len(items) == 4

    events = db.query(CardEvent).filter(
        CardEvent.card_id.in_([commercial_card.id, free_card.id])
    ).all()
    assert sum(event.event_type == "printed_to_pos" for event in events) == 1
    assert sum(event.event_type == "printed_free" for event in events) == 1
    assert sum(event.event_type == "reprinted" for event in events) == 2
    assert all(event.actor == actor for event in events)
    db.close()


def test_print_idempotency_key_cannot_be_reused_for_different_payload(owner_client):
    client, headers, _ = owner_client
    code = "IDEMP-" + secrets.token_hex(4).upper()
    plan = client.post(
        "/api/v1/plans",
        headers=headers,
        json={"code": code, "name": "Idempotency plan", "price": "5.00"},
    )
    assert plan.status_code == 201, plan.text

    usernames = ["IDEM" + secrets.token_hex(4).upper() for _ in range(2)]
    card_ids = []
    for username in usernames:
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
        card_ids.append(created.json()["id"])

    db = SessionLocal()
    pos = PointOfSale(
        code="POS-" + secrets.token_hex(4).upper(),
        name="CI idempotency point",
        is_active=True,
    )
    db.add(pos)
    db.commit()
    pos_id = pos.id
    db.close()

    key = "same-key-" + secrets.token_hex(8)
    first = client.post(
        "/api/v1/print-jobs",
        headers=headers,
        json={"idempotency_key": key, "point_of_sale_id": pos_id, "card_ids": [card_ids[0]]},
    )
    assert first.status_code == 201, first.text

    conflict = client.post(
        "/api/v1/print-jobs",
        headers=headers,
        json={"idempotency_key": key, "point_of_sale_id": pos_id, "card_ids": [card_ids[1]]},
    )
    assert conflict.status_code == 409
