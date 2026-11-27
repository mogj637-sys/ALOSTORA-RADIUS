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
            "card_type": "separate_credentials",
            "password": "SALEpass123",
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
    printed_commercial = next(item for item in first_data["items"] if item["card_id"] == commercial.json()["id"])
    assert printed_commercial["password"] == "SALEpass123"

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
    assert free_card.status == "printed_free"

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


def test_card_batch_persists_template_pos_and_print_preferences(owner_client):
    client, headers, _ = owner_client
    plan = client.post(
        "/api/v1/plans",
        headers=headers,
        json={"code": "BATCH-" + secrets.token_hex(4).upper(), "name": "Linked batch plan", "price": "25.00"},
    )
    assert plan.status_code == 201, plan.text
    plan_id = plan.json()["id"]

    point = client.post(
        "/api/v1/points-of-sale",
        headers=headers,
        json={"code": "POS-" + secrets.token_hex(4).upper(), "name": "Batch point"},
    )
    assert point.status_code == 201, point.text
    point_id = point.json()["id"]

    template_code = "TPL-" + secrets.token_hex(4).upper()
    template = client.post(
        "/api/v1/card-templates",
        headers=headers,
        json={"code": template_code, "name": "Linked template", "plan_id": plan_id},
    )
    assert template.status_code == 201, template.text
    assert template.json()["plan_id"] == plan_id

    created = client.post(
        "/api/v1/cards/batch",
        headers=headers,
        json={
            "plan_id": plan_id,
            "quantity": 2,
            "card_type": "username_only",
            "generation_mode": "digits",
            "username_length": 8,
            "template_code": template_code,
            "point_of_sale_id": point_id,
        },
    )
    assert created.status_code == 201, created.text
    payload = created.json()
    assert payload["batch_number"].startswith("BAT")
    assert payload["template_code"] == template_code
    assert payload["point_of_sale_id"] == point_id
    assert len(payload["cards"]) == 2

    batch_list = client.get("/api/v1/cards/batches", headers=headers)
    assert batch_list.status_code == 200, batch_list.text
    saved_batch = next(item for item in batch_list.json() if item["batch_id"] == payload["batch_id"])
    assert saved_batch["quantity"] == 2
    assert saved_batch["plan_name"] == "Linked batch plan"
    assert saved_batch["point_of_sale_name"] == "Batch point"

    filtered_cards = client.get(
        f"/api/v1/cards?batch_id={payload['batch_id']}",
        headers=headers,
    )
    assert filtered_cards.status_code == 200, filtered_cards.text
    assert len(filtered_cards.json()) == 2

    other_point = client.post(
        "/api/v1/points-of-sale",
        headers=headers,
        json={"code": "POS-" + secrets.token_hex(4).upper(), "name": "Other batch point"},
    )
    assert other_point.status_code == 201, other_point.text
    print_payload = {
        "idempotency_key": "batch-print-" + secrets.token_hex(8),
        "point_of_sale_id": other_point.json()["id"],
        "card_ids": [item["id"] for item in payload["cards"]],
        "template_code": template_code,
    }
    rejected = client.post("/api/v1/print-jobs", headers=headers, json=print_payload)
    assert rejected.status_code == 409

    print_payload["point_of_sale_id"] = point_id
    print_payload["idempotency_key"] = "batch-print-" + secrets.token_hex(8)
    print_payload["print_options"] = {"show_username": False, "show_password": True}
    printed = client.post("/api/v1/print-jobs", headers=headers, json=print_payload)
    assert printed.status_code == 201, printed.text
    assert printed.json()["print_options"]["show_username"] is False
    assert printed.json()["print_options"]["show_password"] is True
    assert printed.json()["items"][0]["plan_name"] == "Linked batch plan"


def test_print_import_resolves_identifiers_across_the_full_database_and_respects_pos_batch_scope(owner_client):
    client, headers, _ = owner_client
    code = "IMPORT-" + secrets.token_hex(4).upper()
    plan = client.post(
        "/api/v1/plans",
        headers=headers,
        json={"code": code, "name": "Import selection plan", "price": "10.00"},
    )
    assert plan.status_code == 201, plan.text

    point_a = client.post(
        "/api/v1/points-of-sale",
        headers=headers,
        json={"code": "IMPORT-A-" + secrets.token_hex(3).upper(), "name": "Import point A"},
    )
    point_b = client.post(
        "/api/v1/points-of-sale",
        headers=headers,
        json={"code": "IMPORT-B-" + secrets.token_hex(3).upper(), "name": "Import point B"},
    )
    assert point_a.status_code == 201, point_a.text
    assert point_b.status_code == 201, point_b.text

    cards = []
    for point in (point_a.json(), point_a.json(), point_b.json()):
        username = "IMPORTED" + secrets.token_hex(5).upper()
        response = client.post(
            "/api/v1/cards/single",
            headers=headers,
            json={
                "plan_id": plan.json()["id"],
                "username": username,
                "card_type": "username_only",
                "point_of_sale_id": point["id"],
            },
        )
        assert response.status_code == 201, response.text
        cards.append(response.json())

    resolved = client.post(
        "/api/v1/cards/print-selection/resolve",
        headers=headers,
        json={
            "point_of_sale_id": point_a.json()["id"],
            "identifiers": [
                cards[0]["username"],
                cards[1]["serial_number"],
                cards[2]["username"],
                "NO-SUCH-CARD",
            ],
        },
    )
    assert resolved.status_code == 200, resolved.text
    data = resolved.json()
    assert data["total_requested"] == 4
    assert data["matched_count"] == 2
    assert {item["id"] for item in data["items"]} == {cards[0]["id"], cards[1]["id"]}
    assert set(data["unmatched"]) == {cards[2]["username"], "NO-SUCH-CARD"}


def test_card_list_reflects_elapsed_validity_even_before_next_radius_packet(owner_client):
    from datetime import datetime, timedelta, timezone

    client, headers, _ = owner_client
    plan = client.post(
        "/api/v1/plans",
        headers=headers,
        json={
            "code": "EXPIRED-" + secrets.token_hex(4).upper(),
            "name": "Expiry display plan",
            "price": "5.00",
            "validity_period_seconds": 3600,
        },
    )
    assert plan.status_code == 201, plan.text
    created = client.post(
        "/api/v1/cards/single",
        headers=headers,
        json={
            "plan_id": plan.json()["id"],
            "username": "EXPIRED" + secrets.token_hex(4).upper(),
            "card_type": "username_only",
        },
    )
    assert created.status_code == 201, created.text

    db = SessionLocal()
    card = db.get(Card, UUID(created.json()["id"]))
    card.first_used_at = datetime.now(timezone.utc) - timedelta(days=2)
    card.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    db.commit()
    db.close()

    expired = client.get("/api/v1/cards?status=expired", headers=headers)
    assert expired.status_code == 200, expired.text
    match = next(item for item in expired.json() if item["id"] == created.json()["id"])
    assert match["status"] == "expired"

    generated = client.get("/api/v1/cards?status=generated", headers=headers)
    assert generated.status_code == 200
    assert all(item["id"] != created.json()["id"] for item in generated.json())

def test_card_list_returns_server_calculated_usage_and_policy_limits(owner_client):
    from datetime import datetime, timedelta, timezone

    client, headers, _ = owner_client
    plan = client.post(
        "/api/v1/plans",
        headers=headers,
        json={
            "code": "USAGE-" + secrets.token_hex(4).upper(),
            "name": "Usage display plan",
            "price": "8.00",
            "data_limit_bytes": 1_000,
            "session_time_limit_seconds": 3_600,
            "validity_period_seconds": 86_400,
            "speed_profile": "usage-test-profile",
            "settings": {
                "shared_users": 3,
                "rate_limit_rx": 1_024,
                "rate_limit_tx": 2_048,
                "rate_limit_unit": "Kbps",
            },
        },
    )
    assert plan.status_code == 201, plan.text

    username = "USAGE" + secrets.token_hex(4).upper()
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

    now = datetime.now(timezone.utc)
    db = SessionLocal()
    card = db.get(Card, UUID(created.json()["id"]))
    card.first_used_at = now - timedelta(hours=1)
    card.expires_at = now + timedelta(seconds=120)
    card.used_seconds = 300
    card.upload_bytes = 100
    card.download_bytes = 200
    db.commit()
    db.close()

    response = client.get(
        f"/api/v1/cards?search={username}",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    match = next(item for item in response.json() if item["id"] == created.json()["id"])

    # The validity deadline caps the remaining session-time allowance.
    assert match["remaining_time_seconds"] <= 120
    assert match["remaining_time_seconds"] > 0
    assert match["remaining_data_bytes"] == 700
    assert match["shared_users_limit"] == 3
    assert match["speed_limit"] == "usage-test-profile"


def test_expired_generated_card_is_excluded_from_print_resolution_and_original_print(owner_client):
    from datetime import datetime, timedelta, timezone

    client, headers, _ = owner_client
    plan = client.post(
        "/api/v1/plans",
        headers=headers,
        json={
            "code": "EXPIRED-PRINT-" + secrets.token_hex(4).upper(),
            "name": "Expired print guard plan",
            "price": "5.00",
            "validity_period_seconds": 3600,
        },
    )
    assert plan.status_code == 201, plan.text

    username = "EXPIRED-PRINT-" + secrets.token_hex(4).upper()
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

    point = client.post(
        "/api/v1/points-of-sale",
        headers=headers,
        json={
            "code": "EXP-PRINT-" + secrets.token_hex(4).upper(),
            "name": "Expired print guard point",
        },
    )
    assert point.status_code == 201, point.text

    now = datetime.now(timezone.utc)
    db = SessionLocal()
    card = db.get(Card, UUID(created.json()["id"]))
    assert card is not None
    card.first_used_at = now - timedelta(days=2)
    card.expires_at = now - timedelta(days=1)
    db.commit()
    db.close()

    resolved = client.post(
        "/api/v1/cards/print-selection/resolve",
        headers=headers,
        json={
            "point_of_sale_id": point.json()["id"],
            "identifiers": [username],
        },
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["matched_count"] == 0
    assert resolved.json()["unmatched"] == [username]

    print_attempt = client.post(
        "/api/v1/print-jobs",
        headers=headers,
        json={
            "idempotency_key": "expired-print-" + secrets.token_hex(12),
            "point_of_sale_id": point.json()["id"],
            "card_ids": [created.json()["id"]],
            "template_code": "green-voucher",
        },
    )
    assert print_attempt.status_code == 409, print_attempt.text
    assert print_attempt.json()["detail"] == "لا يمكن تنفيذ طباعة أصلية لكرت انتهت صلاحيته"
