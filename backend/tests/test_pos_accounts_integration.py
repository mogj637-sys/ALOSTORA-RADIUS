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
    row = next(item for item in data["points"] if item["point_of_sale_id"] == point["id"])
    assert row["point_of_sale_id"] == point["id"]
    assert Decimal(row["delivered_value"]) == Decimal("0.00")
    assert Decimal(row["other_debits"]) == Decimal("100.00")
    assert Decimal(row["commissions"]) == Decimal("10.00")
    assert Decimal(row["payments"]) == Decimal("20.00")
    assert Decimal(row["period_debit"]) == Decimal("100.00")
    assert Decimal(row["period_credit"]) == Decimal("30.00")
    assert Decimal(row["closing_balance"]) == Decimal("70.00")
    assert Decimal(data["totals"]["closing_balance"]) == sum(\n        (Decimal(item["closing_balance"]) for item in data["points"]), Decimal("0.00")\n    )


def test_point_of_sale_report_rejects_reversed_date_range(owner_client):
    client, headers, _ = owner_client
    response = client.get(
        "/api/v1/reports/points-of-sale?date_from=2026-11-15&date_to=2026-11-14",
        headers=headers,
    )
    assert response.status_code == 422



def test_point_of_sale_statement_and_excel_exports(owner_client):
    from datetime import date

    client, headers, _ = owner_client
    point = _point(client, headers)
    base = f"/api/v1/points-of-sale/{point['id']}/account/entries"
    for payload in [
        {
            "idempotency_key": "statement-debit-" + secrets.token_hex(8),
            "entry_type": "adjustment", "direction": "debit", "amount": "80.00",
            "description": "توريد كروت", "reference": "INV-01",
        },
        {
            "idempotency_key": "statement-credit-" + secrets.token_hex(8),
            "entry_type": "payment", "direction": "credit", "amount": "30.00",
            "description": "سداد نقدي", "reference": "PAY-01",
        },
    ]:
        response = client.post(base, headers=headers, json=payload)
        assert response.status_code == 201, response.text

    today = date.today().isoformat()
    query = f"date_from={today}&date_to={today}"
    statement = client.get(
        f"/api/v1/reports/points-of-sale/{point['id']}/statement?{query}",
        headers=headers,
    )
    assert statement.status_code == 200, statement.text
    data = statement.json()
    assert data["point_of_sale_name"] == point["name"]
    assert len(data["entries"]) == 2
    assert Decimal(data["opening_balance"]) == Decimal("0.00")
    assert Decimal(data["total_debit"]) == Decimal("80.00")
    assert Decimal(data["total_credit"]) == Decimal("30.00")
    assert Decimal(data["closing_balance"]) == Decimal("50.00")
    assert Decimal(data["entries"][0]["running_balance"]) == Decimal("80.00")
    assert Decimal(data["entries"][1]["running_balance"]) == Decimal("50.00")

    report_file = client.get(
        f"/api/v1/reports/points-of-sale/export.xlsx?{query}",
        headers=headers,
    )
    assert report_file.status_code == 200, report_file.text
    assert "spreadsheetml" in report_file.headers["content-type"]
    assert report_file.content[:2] == b"PK"

    statement_file = client.get(
        f"/api/v1/reports/points-of-sale/{point['id']}/statement/export.xlsx?{query}",
        headers=headers,
    )
    assert statement_file.status_code == 200, statement_file.text
    assert "spreadsheetml" in statement_file.headers["content-type"]
    assert statement_file.content[:2] == b"PK"


def test_point_of_sale_statement_requires_existing_point(owner_client):
    client, headers, _ = owner_client
    response = client.get(
        "/api/v1/reports/points-of-sale/999999/statement?date_from=2026-11-15&date_to=2026-11-15",
        headers=headers,
    )
    assert response.status_code == 404
