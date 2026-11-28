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
    assert Decimal(data["totals"]["closing_balance"]) == sum(
        (Decimal(item["closing_balance"]) for item in data["points"]), Decimal("0.00")
    )


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


def _create_finance_permission_user(client, owner_headers, permissions, point_ids):
    import secrets

    role_code = "ci_finance_" + secrets.token_hex(4)
    username = "ci_finance_" + secrets.token_hex(4)
    password = "ci-finance-user-password-123"
    role = client.post(
        "/api/v1/admins/roles",
        headers=owner_headers,
        json={"code": role_code, "name": "CI Finance Operations"},
    )
    assert role.status_code == 201, role.text
    granted = client.put(
        f"/api/v1/admins/roles/{role_code}/permissions",
        headers=owner_headers,
        json={"permission_codes": permissions},
    )
    assert granted.status_code == 200, granted.text
    created = client.post(
        "/api/v1/admins",
        headers=owner_headers,
        json={
            "username": username,
            "display_name": "CI Finance Operations",
            "password": password,
            "role_codes": [role_code],
            "point_of_sale_ids": point_ids,
        },
    )
    assert created.status_code == 201, created.text
    login = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert login.status_code == 200, login.text
    return role_code, username, {
        "Authorization": f"Bearer {login.json()['access_token']}"
    }


def _cleanup_finance_permission_user(role_code, username):
    from app.db.session import SessionLocal
    from app.models.auth import AdminUser, Role

    db = SessionLocal()
    user = db.query(AdminUser).filter_by(username=username).first()
    if user is not None:
        user.roles = []
        user.point_of_sales = []
        db.delete(user)
    role = db.query(Role).filter_by(code=role_code).first()
    if role is not None:
        role.permissions = []
        db.delete(role)
    db.commit()
    db.close()


def test_finance_update_is_metadata_only_and_works_without_finance_view(owner_client):
    client, owner_headers, _ = owner_client
    point = _point(client, owner_headers)
    other_point = _point(client, owner_headers)
    account_url = f"/api/v1/points-of-sale/{point['id']}/account"
    other_url = f"/api/v1/points-of-sale/{other_point['id']}/account"
    created = client.post(
        account_url + "/entries",
        headers=owner_headers,
        json={
            "idempotency_key": "finance-update-" + secrets.token_hex(8),
            "entry_type": "adjustment",
            "direction": "debit",
            "amount": "80.00",
            "description": "وصف قبل المراجعة",
            "reference": "OLD-REF",
        },
    )
    assert created.status_code == 201, created.text
    entry_id = created.json()["id"]

    role_code, username, headers = _create_finance_permission_user(
        client, owner_headers, ["finance.update"], [point["id"]]
    )
    try:
        options = client.get(
            "/api/v1/points-of-sale/operation-options?operation=finance.update",
            headers=headers,
        )
        assert options.status_code == 200, options.text
        assert [item["id"] for item in options.json()] == [point["id"]]
        assert client.get(
            "/api/v1/points-of-sale/operation-options?operation=finance.delete",
            headers=headers,
        ).status_code == 403

        search = client.get(
            account_url + f"/entries/operation-options?operation=finance.update&query={entry_id}",
            headers=headers,
        )
        assert search.status_code == 200, search.text
        assert len(search.json()) == 1
        assert search.json()[0]["id"] == entry_id
        assert "idempotency_key" not in search.json()[0]
        assert "created_by" not in search.json()[0]

        assert client.get(account_url, headers=headers).status_code == 403
        assert client.get(account_url + "/entries", headers=headers).status_code == 403

        updated = client.patch(
            account_url + f"/entries/{entry_id}",
            headers=headers,
            json={"description": "وصف بعد المراجعة", "reference": "NEW-REF"},
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["description"] == "وصف بعد المراجعة"
        assert updated.json()["reference"] == "NEW-REF"
        assert updated.json()["amount"] == "80.00"
        assert updated.json()["direction"] == "debit"
        assert "idempotency_key" not in updated.json()
        assert "created_by" not in updated.json()

        forbidden_amount_change = client.patch(
            account_url + f"/entries/{entry_id}",
            headers=headers,
            json={"amount": "1.00"},
        )
        assert forbidden_amount_change.status_code == 422

        cross_point = client.patch(
            other_url + f"/entries/{entry_id}",
            headers=headers,
            json={"description": "محاولة خارج النطاق"},
        )
        assert cross_point.status_code == 403
    finally:
        _cleanup_finance_permission_user(role_code, username)


def test_finance_delete_creates_one_audited_compensating_entry(owner_client):
    from datetime import date

    client, owner_headers, _ = owner_client
    point = _point(client, owner_headers)
    account_url = f"/api/v1/points-of-sale/{point['id']}/account"
    original_response = client.post(
        account_url + "/entries",
        headers=owner_headers,
        json={
            "idempotency_key": "finance-reverse-" + secrets.token_hex(8),
            "entry_type": "payment",
            "direction": "credit",
            "amount": "45.00",
            "description": "سداد نقدي",
            "reference": "PAY-REV-01",
        },
    )
    assert original_response.status_code == 201, original_response.text
    original = original_response.json()

    role_code, username, headers = _create_finance_permission_user(
        client, owner_headers, ["finance.delete"], [point["id"]]
    )
    try:
        options = client.get(
            "/api/v1/points-of-sale/operation-options?operation=finance.delete",
            headers=headers,
        )
        assert options.status_code == 200, options.text
        assert [item["id"] for item in options.json()] == [point["id"]]
        assert client.get(
            "/api/v1/points-of-sale/operation-options?operation=finance.update",
            headers=headers,
        ).status_code == 403

        search = client.get(
            account_url + f"/entries/operation-options?operation=finance.delete&query={original['id']}",
            headers=headers,
        )
        assert search.status_code == 200, search.text
        assert len(search.json()) == 1
        assert search.json()[0]["id"] == original["id"]
        assert client.get(account_url + "/entries", headers=headers).status_code == 403

        reversal_key = "reverse-" + secrets.token_hex(10)
        reverse_url = account_url + f"/entries/{original['id']}/reverse"
        reversed_response = client.post(
            reverse_url,
            headers=headers,
            json={"idempotency_key": reversal_key, "reason": "مراجعة مالية"},
        )
        assert reversed_response.status_code == 201, reversed_response.text
        reversal = reversed_response.json()
        assert reversal["reversal_of_id"] == original["id"]
        assert reversal["entry_type"] == original["entry_type"]
        assert reversal["direction"] == "debit"
        assert reversal["amount"] == original["amount"]
        assert "idempotency_key" not in reversal
        assert "created_by" not in reversal

        changed_reason_replay = client.post(
            reverse_url,
            headers=headers,
            json={"idempotency_key": reversal_key, "reason": "سبب مختلف"},
        )
        assert changed_reason_replay.status_code == 409

        replay = client.post(
            reverse_url,
            headers=headers,
            json={"idempotency_key": reversal_key, "reason": "مراجعة مالية"},
        )
        assert replay.status_code == 201
        assert replay.json()["id"] == reversal["id"]

        second_reversal = client.post(
            reverse_url,
            headers=headers,
            json={"idempotency_key": "reverse-again-" + secrets.token_hex(8)},
        )
        assert second_reversal.status_code == 409

        reverse_the_reversal = client.post(
            account_url + f"/entries/{reversal['id']}/reverse",
            headers=headers,
            json={"idempotency_key": "reverse-chain-" + secrets.token_hex(8)},
        )
        assert reverse_the_reversal.status_code == 409

        assert client.patch(
            account_url + f"/entries/{original['id']}",
            headers=headers,
            json={"description": "تعديل بلا صلاحية"},
        ).status_code == 403
        assert client.get(account_url, headers=headers).status_code == 403
    finally:
        _cleanup_finance_permission_user(role_code, username)

    entries = client.get(account_url + "/entries", headers=owner_headers)
    assert entries.status_code == 200, entries.text
    assert len(entries.json()) == 2
    original_after = next(item for item in entries.json() if item["id"] == original["id"])
    reversal_after = next(item for item in entries.json() if item["id"] == reversal["id"])
    assert original_after["direction"] == "credit"
    assert original_after["amount"] == "45.00"
    assert original_after["reversed_by_id"] == reversal["id"]
    assert reversal_after["reversal_of_id"] == original["id"]

    summary = client.get(account_url, headers=owner_headers)
    assert summary.status_code == 200
    assert Decimal(summary.json()["total_debit"]) == Decimal("45.00")
    assert Decimal(summary.json()["total_credit"]) == Decimal("45.00")
    assert Decimal(summary.json()["balance_due"]) == Decimal("0.00")

    today = date.today().isoformat()
    report = client.get(
        f"/api/v1/reports/points-of-sale?date_from={today}&date_to={today}",
        headers=owner_headers,
    )
    assert report.status_code == 200, report.text
    row = next(item for item in report.json()["points"] if item["point_of_sale_id"] == point["id"])
    assert Decimal(row["payments"]) == Decimal("0.00")

    from app.db.session import SessionLocal
    from app.models.audit import AuditLog

    audit_db = SessionLocal()
    audit = audit_db.query(AuditLog).filter_by(
        action="finance.entry_reversed",
        entity_type="pos_account_entry",
        entity_id=str(reversal["id"]),
    ).one()
    assert audit.details["original_entry_id"] == original["id"]
    assert audit.details["reversal_entry_id"] == reversal["id"]
    audit_db.close()


def test_finance_delete_cannot_reverse_print_generated_commission(owner_client):
    client, owner_headers, _ = owner_client
    point = _point(client, owner_headers)
    account_url = f"/api/v1/points-of-sale/{point['id']}/account"
    created = client.post(
        account_url + "/entries",
        headers=owner_headers,
        json={
            "idempotency_key": "finance-commission-" + secrets.token_hex(8),
            "entry_type": "commission",
            "direction": "credit",
            "amount": "7.50",
            "description": "عمولة مرتبطة بالطباعة",
        },
    )
    assert created.status_code == 201, created.text

    role_code, username, headers = _create_finance_permission_user(
        client, owner_headers, ["finance.delete"], [point["id"]]
    )
    try:
        blocked = client.post(
            account_url + f"/entries/{created.json()['id']}/reverse",
            headers=headers,
            json={"idempotency_key": "blocked-reversal-" + secrets.token_hex(8)},
        )
        assert blocked.status_code == 409
    finally:
        _cleanup_finance_permission_user(role_code, username)
