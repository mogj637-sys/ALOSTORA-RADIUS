import secrets
from decimal import Decimal


def _point(client, headers):
    response = client.post(
        "/api/v1/points-of-sale",
        headers=headers,
        json={"code": "ACC-" + secrets.token_hex(4).upper(), "name": "نقطة حسابية"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_point_of_sale_ledger_balance_and_idempotency(owner_client):
    client, headers, _ = owner_client
    point = _point(client, headers)
    url = f"/api/v1/points-of-sale/{point['id']}/account"

    debit_payload = {
        "idempotency_key": "debit-" + secrets.token_hex(10),
        "entry_type": "adjustment",
        "direction": "debit",
        "amount": "125.50",
        "description": "قيمة كروت مستلمة",
    }
    first = client.post(url + "/entries", headers=headers, json=debit_payload)
    assert first.status_code == 201, first.text
    duplicate = client.post(url + "/entries", headers=headers, json=debit_payload)
    assert duplicate.status_code == 201, duplicate.text
    assert duplicate.json()["id"] == first.json()["id"]

    credit_payload = {
        "idempotency_key": "credit-" + secrets.token_hex(10),
        "entry_type": "payment",
        "direction": "credit",
        "amount": "25.50",
        "description": "سداد نقدي",
    }
    credit = client.post(url + "/entries", headers=headers, json=credit_payload)
    assert credit.status_code == 201, credit.text

    summary = client.get(url, headers=headers)
    assert summary.status_code == 200, summary.text
    assert Decimal(summary.json()["total_debit"]) == Decimal("125.50")
    assert Decimal(summary.json()["total_credit"]) == Decimal("25.50")
    assert Decimal(summary.json()["balance_due"]) == Decimal("100.00")

    changed_replay = client.post(
        url + "/entries",
        headers=headers,
        json={**debit_payload, "amount": "126.00"},
    )
    assert changed_replay.status_code == 409

    entries = client.get(url + "/entries", headers=headers)
    assert entries.status_code == 200
    assert len(entries.json()) == 2


def test_point_of_sale_ledger_rejects_nonpositive_amount(owner_client):
    client, headers, _ = owner_client
    point = _point(client, headers)
    response = client.post(
        f"/api/v1/points-of-sale/{point['id']}/account/entries",
        headers=headers,
        json={
            "idempotency_key": "invalid-" + secrets.token_hex(10),
            "entry_type": "payment",
            "direction": "credit",
            "amount": "0",
        },
    )
    assert response.status_code == 422
