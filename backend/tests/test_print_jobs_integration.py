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

    db = SessionLocal()
    saved = db.get(Card, UUID(free_card["id"]))
    assert saved is not None
    assert saved.assigned_pos_id is None
    assert saved.status == "generated"
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
