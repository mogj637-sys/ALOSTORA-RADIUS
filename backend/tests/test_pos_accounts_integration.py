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


def test_point_of_sale_report_summarizes_period_movements(owner_client):
    from datetime import date

    client, headers, _ = owner_client
    point = _point(client, headers)
    account_url = f"/api/v1/points-of-sale/{point['id']}/account/entries"

    entries = [
        {
            "idempotency_key": "report-debit-" + secrets.token_hex(8),
            "entry_type": "adjustment",
            "direction": "debit",
            "amount": "100.00",
            "description": "رصيد سابق داخل الفترة",
        },
        {
            "idempotency_key": "report-commission-" + secrets.token_hex(8),
            "entry_type": "commission",
            "direction": "credit",
            "amount": "10.00",
            "description": "عمولة الباقة",
        },
        {
            "idempotency_key": "report-payment-" + secrets.token_hex(8),
            "entry_type": "payment",
            "direction": "credit",
            "amount": "20.00",
            "description": "سداد",
        },
    ]
    for payload in entries:
        response = client.post(account_url, headers=headers, json=payload)
        assert response.status_code == 201, response.text

    today = date.today().isoformat()
    report = client.get(
        f"/api/v1/reports/points-of-sale?date_from={today}&date_to={today}",
        headers=headers,
    )
    assert report.status_code == 200, report.text
    data = report.json()
    assert data["point_count"] == 1
    assert len(data["points"]) == 1
    row = data["points"][0]
    assert row["point_of_sale_id"] == point["id"]
    assert Decimal(row["delivered_value"]) == Decimal("0.00")
    assert Decimal(row["other_debits"]) == Decimal("100.00")
    assert Decimal(row["commissions"]) == Decimal("10.00")
    assert Decimal(row["payments"]) == Decimal("20.00")
    assert Decimal(row["period_debit"]) == Decimal("100.00")
    assert Decimal(row["period_credit"]) == Decimal("30.00")
    assert Decimal(row["closing_balance"]) == Decimal("70.00")
    assert Decimal(data["totals"]["closing_balance"]) == Decimal("70.00")


def test_point_of_sale_report_rejects_reversed_date_range(owner_client):
    client, headers, _ = owner_client
    response = client.get(
        "/api/v1/reports/points-of-sale?date_from=2026-11-15&date_to=2026-11-14",
        headers=headers,
    )
    assert response.status_code == 422
