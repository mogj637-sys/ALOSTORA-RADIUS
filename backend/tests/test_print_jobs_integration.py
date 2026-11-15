import secrets
from decimal import Decimal
from uuid import UUID

from app.db.session import SessionLocal
from app.models.core import Card, PosInventoryMovement, PrintJobItem

def _plan(client, headers):
    response = client.post(
        "/api/v1/plans",
        headers=headers,
        json={
            "code": "PRINT-" + secrets.token_hex(4).upper(),
            "name": "Print integration plan",
            "price": "25.00",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _card(client, headers, plan_id, *, free=False):
    username = ("FREE" if free else "SALE") + secrets.token_hex(5).upper()
    response = client.post(
        "/api/v1/cards/single",
        headers=headers,
        json={
            "plan_id": plan_id,
            "username": username,
            "card_type": "username_only",
            "is_free": free,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _point(client, headers):
    response = client.post(
        "/api/v1/points-of-sale",
        headers=headers,
        json={
            "code": "POS-" + secrets.token_hex(4).upper(),
            "name": "نقطة اختبار",
            "contact_name": "مسؤول الاختبار",
            "phone": "700000000",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_print_allocation_is_idempotent_and_reprint_does_not_duplicate_stock(owner_client):
    client, headers, actor = owner_client
    plan_id = _plan(client, headers)
    point = _point(client, headers)
    cards = [_card(client, headers, plan_id) for _ in range(2)]
    card_ids = [item["id"] for item in cards]
    key = "print-" + secrets.token_hex(12)

    payload = {
        "idempotency_key": key,
        "point_of_sale_id": point["id"],
        "card_ids": card_ids,
        "template_code": "classic-green",
    }
    first = client.post("/api/v1/print-jobs", headers=headers, json=payload)
    assert first.status_code == 201, first.text
    assert "no-store" in first.headers.get("cache-control", "")
    result = first.json()
    assert result["card_count"] == 2
    assert result["commercial_card_count"] == 2
    assert result["free_card_count"] == 0
    assert Decimal(result["total_amount"]) == Decimal("50.00")

    repeated = client.post("/api/v1/print-jobs", headers=headers, json=payload)
    assert repeated.status_code == 201, repeated.text
    assert repeated.json()["id"] == result["id"]

    reprint_payload = {
        **payload,
        "idempotency_key": "reprint-" + secrets.token_hex(12),
        "is_reprint": True,
    }
    reprinted = client.post("/api/v1/print-jobs", headers=headers, json=reprint_payload)
    assert reprinted.status_code == 201, reprinted.text
    assert reprinted.json()["is_reprint"] is True
    assert Decimal(reprinted.json()["total_amount"]) == Decimal("0.00")

    history = client.get(
        f"/api/v1/print-jobs?point_of_sale_id={point['id']}",
        headers=headers,
    )
    assert history.status_code == 200, history.text
    assert len(history.json()) == 2
    assert all("password" not in item["cards"][0] for item in history.json())

    cannot_cancel_printed = client.patch(
        f"/api/v1/cards/{card_ids[0]}/status",
        headers=headers,
        json={"action": "cancel"},
    )
    assert cannot_cancel_printed.status_code == 409

    db = SessionLocal()
    saved_cards = db.query(Card).filter(Card.id.in_([UUID(value) for value in card_ids])).all()
    assert len(saved_cards) == 2
    assert all(card.assigned_pos_id == point["id"] for card in saved_cards)
    assert all(card.status == "allocated" for card in saved_cards)
    movements = db.query(PosInventoryMovement).filter(
        PosInventoryMovement.card_id.in_([UUID(value) for value in card_ids])
    ).all()
    assert len(movements) == 2
    assert sum((movement.amount for movement in movements), Decimal("0.00")) == Decimal("50.00")
    original_items = db.query(PrintJobItem).filter(
        PrintJobItem.print_job_id == UUID(result["id"])
    ).count()
    assert original_items == 2
    db.close()

    inventory = client.get(
        f"/api/v1/points-of-sale/{point['id']}/inventory",
        headers=headers,
    )
    assert inventory.status_code == 200, inventory.text
    assert inventory.json()["allocated_cards"] == 2
    assert Decimal(inventory.json()["commercial_printed_value"]) == Decimal("50.00")

    account = client.get(
        f"/api/v1/points-of-sale/{point['id']}/account", headers=headers
    )
    assert account.status_code == 200, account.text
    assert Decimal(account.json()["total_debit"]) == Decimal("50.00")
    assert Decimal(account.json()["total_credit"]) == Decimal("0.00")
    assert Decimal(account.json()["balance_due"]) == Decimal("50.00")


def test_free_card_print_is_recorded_but_not_allocated_or_charged(owner_client):
    client, headers, _ = owner_client
    plan_id = _plan(client, headers)
    point = _point(client, headers)
    free_card = _card(client, headers, plan_id, free=True)

    response = client.post(
        "/api/v1/print-jobs",
        headers=headers,
        json={
            "idempotency_key": "free-print-" + secrets.token_hex(12),
            "point_of_sale_id": point["id"],
            "card_ids": [free_card["id"]],
            "template_code": "free-green",
        },
    )
    assert response.status_code == 201, response.text
    result = response.json()
    assert result["free_card_count"] == 1
    assert result["commercial_card_count"] == 0
    assert Decimal(result["total_amount"]) == Decimal("0.00")

    duplicate_original = client.post(
        "/api/v1/print-jobs",
        headers=headers,
        json={
            "idempotency_key": "free-duplicate-" + secrets.token_hex(12),
            "point_of_sale_id": point["id"],
            "card_ids": [free_card["id"]],
        },
    )
    assert duplicate_original.status_code == 409

    db = SessionLocal()
    saved = db.get(Card, UUID(free_card["id"]))
    assert saved is not None
    assert saved.assigned_pos_id is None
    assert saved.status == "printed_free"
    assert db.query(PosInventoryMovement).filter(
        PosInventoryMovement.card_id == UUID(free_card["id"])
    ).count() == 0
    db.close()

    inventory = client.get(
        f"/api/v1/points-of-sale/{point['id']}/inventory",
        headers=headers,
    )
    assert inventory.status_code == 200, inventory.text
    assert inventory.json()["free_cards_printed"] == 1
    assert inventory.json()["allocated_cards"] == 0

    account = client.get(
        f"/api/v1/points-of-sale/{point['id']}/account", headers=headers
    )
    assert account.status_code == 200, account.text
    assert Decimal(account.json()["total_debit"]) == Decimal("0.00")
    assert Decimal(account.json()["balance_due"]) == Decimal("0.00")


def test_card_cannot_be_allocated_to_two_points_of_sale(owner_client):
    client, headers, _ = owner_client
    plan_id = _plan(client, headers)
    first_point = _point(client, headers)
    second_point = _point(client, headers)
    card = _card(client, headers, plan_id)

    first = client.post(
        "/api/v1/print-jobs",
        headers=headers,
        json={
            "idempotency_key": "alloc-a-" + secrets.token_hex(10),
            "point_of_sale_id": first_point["id"],
            "card_ids": [card["id"]],
        },
    )
    assert first.status_code == 201, first.text

    second = client.post(
        "/api/v1/print-jobs",
        headers=headers,
        json={
            "idempotency_key": "alloc-b-" + secrets.token_hex(10),
            "point_of_sale_id": second_point["id"],
            "card_ids": [card["id"]],
        },
    )
    assert second.status_code == 409


def test_print_response_reveals_credentials_only_in_authorized_print_flow(owner_client):
    client, headers, _ = owner_client
    plan_id = _plan(client, headers)
    point = _point(client, headers)
    username = "SECRET" + secrets.token_hex(4).upper()
    password = "private-print-password"
    created = client.post(
        "/api/v1/cards/single",
        headers=headers,
        json={
            "plan_id": plan_id,
            "username": username,
            "card_type": "separate_credentials",
            "password": password,
        },
    )
    assert created.status_code == 201, created.text

    card_list = client.get("/api/v1/cards?search=" + username, headers=headers)
    assert card_list.status_code == 200
    assert len(card_list.json()) == 1
    assert "password" not in card_list.json()[0]
    assert "credential_ciphertext" not in card_list.json()[0]

    printed = client.post(
        "/api/v1/print-jobs",
        headers=headers,
        json={
            "idempotency_key": "secret-print-" + secrets.token_hex(10),
            "point_of_sale_id": point["id"],
            "card_ids": [created.json()["id"]],
        },
    )
    assert printed.status_code == 201, printed.text
    assert "no-store" in printed.headers.get("cache-control", "")
    assert printed.json()["items"][0]["password"] == password

    history = client.get(
        f"/api/v1/print-jobs?point_of_sale_id={point['id']}",
        headers=headers,
    )
    assert history.status_code == 200, history.text
    assert len(history.json()) == 1
    history_card = history.json()[0]["cards"][0]
    assert history_card["username"] == username
    assert "password" not in history_card


def test_free_card_lifecycle_and_protect_pos_allocated_card_from_cancellation(owner_client):
    client, headers, _ = owner_client
    plan_id = _plan(client, headers)
    point = _point(client, headers)
    free_card = _card(client, headers, plan_id, free=True)
    sale_card = _card(client, headers, plan_id, free=False)

    printed = client.post(
        "/api/v1/print-jobs",
        headers=headers,
        json={
            "idempotency_key": "mixed-" + secrets.token_hex(10),
            "point_of_sale_id": point["id"],
            "card_ids": [free_card["id"], sale_card["id"]],
            "template_code": "classic-green",
        },
    )
    assert printed.status_code == 201, printed.text

    free_suspended = client.patch(
        f"/api/v1/cards/{free_card['id']}/status",
        headers=headers,
        json={"action": "suspend"},
    )
    assert free_suspended.status_code == 200, free_suspended.text
    free_restored = client.patch(
        f"/api/v1/cards/{free_card['id']}/status",
        headers=headers,
        json={"action": "reactivate"},
    )
    assert free_restored.status_code == 200, free_restored.text
    assert free_restored.json()["status"] == "printed_free"

    free_cancelled = client.patch(
        f"/api/v1/cards/{free_card['id']}/status",
        headers=headers,
        json={"action": "cancel"},
    )
    assert free_cancelled.status_code == 200, free_cancelled.text

    allocated_cancel = client.patch(
        f"/api/v1/cards/{sale_card['id']}/status",
        headers=headers,
        json={"action": "cancel"},
    )
    assert allocated_cancel.status_code == 409
