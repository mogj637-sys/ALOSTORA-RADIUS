import secrets

from app.db.session import SessionLocal
from app.models.auth import AdminUser


def test_card_batch_can_extend_compatible_previous_batch(owner_client):
    client, headers, _ = owner_client
    suffix = secrets.token_hex(4).upper()
    plan = client.post(
        "/api/v1/plans",
        headers=headers,
        json={
            "code": f"LINK-{suffix}",
            "name": "باقة ربط الدفعات",
            "price": "25.00",
        },
    )
    assert plan.status_code == 201, plan.text

    point = client.post(
        "/api/v1/points-of-sale",
        headers=headers,
        json={"code": f"LINK-{suffix}", "name": "نقطة ربط الدفعات"},
    )
    assert point.status_code == 201, point.text

    template = client.post(
        "/api/v1/card-templates",
        headers=headers,
        json={
            "code": f"LINK-{suffix}",
            "name": "قالب ربط الدفعات",
            "plan_id": plan.json()["id"],
        },
    )
    assert template.status_code == 201, template.text

    common = {
        "plan_id": plan.json()["id"],
        "card_type": "username_only",
        "generation_mode": "digits",
        "username_length": 8,
        "password_length": 10,
        "prefix": "77",
        "template_code": template.json()["code"],
        "point_of_sale_id": point.json()["id"],
    }
    first = client.post(
        "/api/v1/cards/batch",
        headers=headers,
        json={**common, "quantity": 2, "note": "الدفعة الأصلية"},
    )
    assert first.status_code == 201, first.text
    batch_id = first.json()["batch_id"]
    assert first.json()["created_count"] == 2

    extension = client.post(
        "/api/v1/cards/batch",
        headers=headers,
        json={
            **common,
            "quantity": 3,
            "existing_batch_number": first.json()["batch_number"],
            "is_online_sale": True,
            "note": "إضافة كمية جديدة",
        },
    )
    assert extension.status_code == 201, extension.text
    assert extension.json()["batch_id"] == batch_id
    assert extension.json()["batch_number"] == first.json()["batch_number"]
    assert extension.json()["created_count"] == 3
    assert extension.json()["is_online_sale"] is True
    assert "الدفعة الأصلية" in extension.json()["note"]
    assert "إضافة كمية جديدة" in extension.json()["note"]

    batches = client.get("/api/v1/cards/batches?limit=200", headers=headers)
    assert batches.status_code == 200, batches.text
    linked = next(item for item in batches.json() if item["batch_id"] == batch_id)
    assert linked["quantity"] == 5
    assert linked["is_online_sale"] is True
    assert linked["generation_mode"] == "digits"
    assert linked["prefix"] == "77"

    incompatible = client.post(
        "/api/v1/cards/batch",
        headers=headers,
        json={
            **common,
            "quantity": 1,
            "prefix": "88",
            "existing_batch_id": batch_id,
        },
    )
    assert incompatible.status_code == 409
