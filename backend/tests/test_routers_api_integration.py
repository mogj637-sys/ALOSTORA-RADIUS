import secrets

from app.db.session import SessionLocal
from app.models.core import Router
from app.services.router_secrets import decrypt_router_secret


def test_router_secrets_are_encrypted_and_never_returned_by_api(owner_client):
    client, headers, _ = owner_client
    nas_id = "nas-" + secrets.token_hex(5)
    radius_secret = "radius-secret-" + secrets.token_hex(8)
    api_secret = "router-api-secret-" + secrets.token_hex(8)
    created = client.post(
        "/api/v1/routers",
        headers=headers,
        json={
            "name": "Router integration test",
            "nas_identifier": nas_id,
            "management_host": "192.0.2.10",
            "api_port": 8729,
            "api_username": "radius-manager",
            "api_secret": api_secret,
            "radius_secret": radius_secret,
            "routeros_version": "7.x",
        },
    )
    assert created.status_code == 201, created.text
    result = created.json()
    assert result["nas_identifier"] == nas_id
    assert result["api_username"] == "radius-manager"
    assert "api_secret" not in result
    assert "radius_secret" not in result
    assert "api_secret_encrypted" not in result
    assert "radius_secret_encrypted" not in result

    db = SessionLocal()
    saved = db.query(Router).filter_by(nas_identifier=nas_id).one()
    assert saved.radius_secret_encrypted != radius_secret
    assert saved.api_secret_encrypted != api_secret
    assert decrypt_router_secret(saved.radius_secret_encrypted) == radius_secret
    assert decrypt_router_secret(saved.api_secret_encrypted) == api_secret
    router_id = saved.id
    db.close()

    listed = client.get("/api/v1/routers", headers=headers)
    assert listed.status_code == 200
    item = next(row for row in listed.json() if row["id"] == router_id)
    assert "radius_secret" not in item
    assert "api_secret" not in item


def test_router_api_credentials_must_be_supplied_as_a_pair(owner_client):
    client, headers, _ = owner_client
    response = client.post(
        "/api/v1/routers",
        headers=headers,
        json={
            "name": "Incomplete router",
            "nas_identifier": "nas-" + secrets.token_hex(5),
            "management_host": "192.0.2.11",
            "api_username": "router-user",
            "radius_secret": "radius-secret-" + secrets.token_hex(8),
        },
    )
    assert response.status_code == 422


def test_router_can_be_deactivated_and_api_credentials_cleared(owner_client):
    client, headers, _ = owner_client
    nas_id = "nas-" + secrets.token_hex(5)
    created = client.post(
        "/api/v1/routers",
        headers=headers,
        json={
            "name": "Router to deactivate",
            "nas_identifier": nas_id,
            "management_host": "192.0.2.12",
            "api_username": "router-user",
            "api_secret": "router-secret-" + secrets.token_hex(8),
            "radius_secret": "radius-secret-" + secrets.token_hex(8),
        },
    )
    assert created.status_code == 201, created.text
    router_id = created.json()["id"]

    updated = client.patch(
        f"/api/v1/routers/{router_id}",
        headers=headers,
        json={"api_username": None, "api_secret": None, "is_active": False},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["is_active"] is False
    assert updated.json()["api_username"] is None

    db = SessionLocal()
    saved = db.get(Router, router_id)
    assert saved.api_secret_encrypted is None
    db.close()

    active = client.get("/api/v1/routers", headers=headers)
    all_routers = client.get("/api/v1/routers?include_inactive=true", headers=headers)
    assert all(row["id"] != router_id for row in active.json())
    assert any(row["id"] == router_id for row in all_routers.json())
