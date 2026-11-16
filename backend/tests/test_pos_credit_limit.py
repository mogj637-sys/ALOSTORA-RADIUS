import secrets
from decimal import Decimal

from app.db.session import SessionLocal
from app.models.core import Card


def _point(client, headers, **settings):
    response = client.post(
        "/api/v1/points-of-sale",
        headers=headers,
        json={
            "code": "CREDIT-" + secrets.token_hex(4).upper(),
            "name": "نقطة سقف مالي",
            **settings,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _plan(client, headers, price="30.00"):
    response = client.post(
        "/api/v1/plans",
        headers=headers,
        json={
            "code": "CREDIT-" + secrets.token_hex(4).upper(),
            "name": "باقة اختبار السقف",
            "price": price,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _card(client, headers, point_id, plan_id):
    response = client.post(
        "/api/v1/cards/single",
        headers=headers,
        json={
            "plan_id": plan_id,
            "username": "CREDIT" + secrets.token_hex(5).upper(),
            "card_type": "username_only",
            "point_of_sale_id": point_id,
        },
    )
    return response


def _print(client, headers, point_id, card_id):
    return client.post(
        "/api/v1/print-jobs",
        headers=headers,
        json={
            "idempotency_key": "credit-print-" + secrets.token_hex(8),
            "point_of_sale_id": point_id,
            "card_ids": [card_id],
        },
    )


def test_pos_debt_limit_blocks_delivery_until_payment_reduces_balance(owner_client):
    client, headers, _ = owner_client
    point = _point(client, headers, debt_limit="50.00")
    plan_id = _plan(client, headers, "30.00")
    first_card = _card(client, headers, point["id"], plan_id)
    second_card = _card(client, headers, point["id"], plan_id)
    assert first_card.status_code == 201, first_card.text
    assert second_card.status_code == 201, second_card.text

    first_print = _print(client, headers, point["id"], first_card.json()["id"])
    assert first_print.status_code == 201, first_print.text
    account_url = f"/api/v1/points-of-sale/{point['id']}/account"
    account = client.get(account_url, headers=headers)
    assert account.status_code == 200
    assert Decimal(account.json()["balance_due"]) == Decimal("30.00")

    over_limit = _print(client, headers, point["id"], second_card.json()["id"])
    assert over_limit.status_code == 409
    assert "سقف المديونية" in over_limit.json()["detail"]

    payment = client.post(
        account_url + "/entries",
        headers=headers,
        json={
            "idempotency_key": "credit-payment-" + secrets.token_hex(8),
            "entry_type": "payment",
            "direction": "credit",
            "amount": "10.00",
            "description": "سداد جزئي لتجربة سقف المديونية",
        },
    )
    assert payment.status_code == 201, payment.text

    allowed_after_payment = _print(client, headers, point["id"], second_card.json()["id"])
    assert allowed_after_payment.status_code == 201, allowed_after_payment.text
    final_account = client.get(account_url, headers=headers)
    assert Decimal(final_account.json()["balance_due"]) == Decimal("50.00")


def test_admin_can_stop_card_creation_and_printing_independently(owner_client):
    client, headers, _ = owner_client
    point = _point(client, headers)
    plan_id = _plan(client, headers)

    stop_creation = client.patch(
        f"/api/v1/points-of-sale/{point['id']}",
        headers=headers,
        json={"allow_card_creation": False},
    )
    assert stop_creation.status_code == 200, stop_creation.text
    assert stop_creation.json()["allow_card_creation"] is False

    blocked_single = _card(client, headers, point["id"], plan_id)
    assert blocked_single.status_code == 409

    batch = client.post(
        "/api/v1/cards/batch",
        headers=headers,
        json={
            "plan_id": plan_id,
            "quantity": 2,
            "card_type": "username_only",
            "generation_mode": "digits",
            "username_length": 8,
            "point_of_sale_id": point["id"],
        },
    )
    assert batch.status_code == 409

    enable_creation = client.patch(
        f"/api/v1/points-of-sale/{point['id']}",
        headers=headers,
        json={"allow_card_creation": True},
    )
    assert enable_creation.status_code == 200, enable_creation.text
    card = _card(client, headers, point["id"], plan_id)
    assert card.status_code == 201, card.text

    stop_printing = client.patch(
        f"/api/v1/points-of-sale/{point['id']}",
        headers=headers,
        json={"allow_printing": False},
    )
    assert stop_printing.status_code == 200, stop_printing.text
    assert stop_printing.json()["allow_printing"] is False

    blocked_print = _print(client, headers, point["id"], card.json()["id"])
    assert blocked_print.status_code == 409

    enable_printing = client.patch(
        f"/api/v1/points-of-sale/{point['id']}",
        headers=headers,
        json={"allow_printing": True},
    )
    assert enable_printing.status_code == 200, enable_printing.text
    allowed_print = _print(client, headers, point["id"], card.json()["id"])
    assert allowed_print.status_code == 201, allowed_print.text
