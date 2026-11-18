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
            "radius_client_address": "192.0.2.10",
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
    assert result["api_use_ssl"] is True
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


def test_internal_radius_clients_endpoint_returns_configured_nas_including_disabled_for_stop_packets(owner_client):
    import os

    client, headers, _ = owner_client
    active_secret = "active-radius-secret-" + secrets.token_hex(8)
    active = client.post(
        "/api/v1/routers",
        headers=headers,
        json={
            "name": "Active NAS",
            "nas_identifier": "nas-active-" + secrets.token_hex(4),
            "management_host": "192.0.2.30",
            "radius_client_address": "192.0.2.30/32",
            "radius_secret": active_secret,
        },
    )
    assert active.status_code == 201, active.text

    inactive_secret = "inactive-radius-secret-" + secrets.token_hex(8)
    inactive = client.post(
        "/api/v1/routers",
        headers=headers,
        json={
            "name": "Inactive NAS",
            "nas_identifier": "nas-inactive-" + secrets.token_hex(4),
            "management_host": "192.0.2.31",
            "radius_client_address": "192.0.2.31",
            "radius_secret": inactive_secret,
            "is_active": False,
        },
    )
    assert inactive.status_code == 201, inactive.text

    clients = client.get(
        "/internal/radius/clients",
        headers={"X-Radius-Internal-Key": os.environ["RADIUS_INTERNAL_API_KEY"]},
    )
    assert clients.status_code == 200, clients.text
    assert "no-store" in clients.headers.get("cache-control", "")
    entries = clients.json()["clients"]
    active_entry = next(item for item in entries if item["nas_identifier"] == active.json()["nas_identifier"])
    assert active_entry["ipaddr"] == "192.0.2.30/32"
    assert active_entry["secret"] == active_secret
    inactive_entry = next(item for item in entries if item["nas_identifier"] == inactive.json()["nas_identifier"])
    assert inactive_entry["ipaddr"] == "192.0.2.31"
    assert inactive_entry["secret"] == inactive_secret


def test_router_rejects_invalid_radius_client_network_and_control_characters(owner_client):
    client, headers, _ = owner_client
    base = {
        "name": "Invalid NAS",
        "nas_identifier": "nas-invalid-" + secrets.token_hex(4),
        "management_host": "192.0.2.40",
        "radius_secret": "radius-secret-" + secrets.token_hex(8),
    }
    bad_network = client.post(
        "/api/v1/routers",
        headers=headers,
        json={**base, "radius_client_address": "192.0.2.40\nclient injected"},
    )
    assert bad_network.status_code == 422

    bad_secret = client.post(
        "/api/v1/routers",
        headers=headers,
        json={**base, "nas_identifier": "nas-control-" + secrets.token_hex(4), "radius_secret": "line1\nline2-secret"},
    )
    assert bad_secret.status_code == 422



def test_router_api_tls_mode_can_be_set_for_custom_port_and_updated(owner_client):
    client, headers, _ = owner_client
    created = client.post(
        "/api/v1/routers",
        headers=headers,
        json={
            "name": "Custom API-SSL port",
            "nas_identifier": "nas-custom-tls-" + secrets.token_hex(4),
            "management_host": "192.0.2.44",
            "api_port": 18729,
            "api_username": "tls-reader",
            "api_secret": "tls-secret-" + secrets.token_hex(8),
            "radius_secret": "radius-secret-" + secrets.token_hex(8),
        },
    )

    assert created.status_code == 201, created.text
    router_id = created.json()["id"]
    assert created.json()["api_port"] == 18729
    assert created.json()["api_use_ssl"] is True

    changed_port = client.patch(
        f"/api/v1/routers/{router_id}",
        headers=headers,
        json={"api_port": 18730},
    )
    assert changed_port.status_code == 200, changed_port.text
    assert changed_port.json()["api_use_ssl"] is True

    standard_port = client.patch(
        f"/api/v1/routers/{router_id}",
        headers=headers,
        json={"api_port": 8728},
    )
    assert standard_port.status_code == 200, standard_port.text
    assert standard_port.json()["api_use_ssl"] is True

    updated = client.patch(
        f"/api/v1/routers/{router_id}",
        headers=headers,
        json={"api_use_ssl": False},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["api_use_ssl"] is False

def test_router_creation_defaults_to_api_ssl(owner_client):
    client, headers, _ = owner_client
    created = client.post(
        "/api/v1/routers",
        headers=headers,
        json={
            "name": "Secure default router",
            "nas_identifier": "nas-secure-default-" + secrets.token_hex(4),
            "management_host": "192.0.2.45",
            "radius_secret": "radius-secret-" + secrets.token_hex(8),
        },
    )

    assert created.status_code == 201, created.text
    assert created.json()["api_port"] == 8729
    assert created.json()["api_use_ssl"] is True
