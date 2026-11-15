import secrets
from uuid import UUID

from app.api import user_manager
from app.db.session import SessionLocal
from app.models.core import Router
from app.models.user_manager import UserManagerSyncRun
from app.models.user_manager_preview import UserManagerImportPreview
from app.services.user_manager_routeros import RouterProbe


def _create_router(client, headers):
    response = client.post(
        "/api/v1/routers",
        headers=headers,
        json={
            "name": "UM probe " + secrets.token_hex(3),
            "nas_identifier": "um-probe-" + secrets.token_hex(4),
            "management_host": "192.0.2.55",
            "api_port": 8728,
            "api_username": "um-reader",
            "api_secret": "api-secret-" + secrets.token_hex(8),
            "radius_secret": "radius-secret-" + secrets.token_hex(8),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_user_manager_probe_returns_read_only_router_inventory(owner_client, monkeypatch):
    client, headers, _ = owner_client
    router_id = _create_router(client, headers)
    seen = {}

    def fake_probe(**kwargs):
        seen.update(kwargs)
        return RouterProbe(
            identity="RB2011-test",
            version="6.49.23 (stable)",
            board_name="RB2011UiAS-2HnD",
            architecture_name="mipsbe",
            uptime="1d2h",
            user_manager_available=True,
            resources={
                "users": {"available": True, "count": 123},
                "profiles": {"available": True, "count": 4},
                "limitations": {"available": True, "count": 2},
                "sessions": {"available": True, "count": 9},
            },
            warnings=["API العادي دون TLS"],
        )

    monkeypatch.setattr(user_manager, "inspect_routeros_user_manager", fake_probe)
    response = client.post(
        f"/api/v1/routers/{router_id}/user-manager/test-connection",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["connected"] is True
    assert data["read_only"] is True
    assert data["routeros_version"] == "6.49.23 (stable)"
    assert data["resources"]["users"]["count"] == 123
    assert "password" not in data
    assert seen["host"] == "192.0.2.55"
    assert seen["username"] == "um-reader"
    assert seen["password"].startswith("api-secret-")


def test_user_manager_probe_requires_owner(owner_client):
    client, _, _ = owner_client
    response = client.post("/api/v1/routers/999/user-manager/test-connection")
    assert response.status_code == 401


def test_user_manager_probe_requires_saved_api_credentials(owner_client):
    client, headers, _ = owner_client
    response = client.post(
        "/api/v1/routers",
        headers=headers,
        json={
            "name": "No API credentials",
            "nas_identifier": "um-no-api-" + secrets.token_hex(4),
            "management_host": "192.0.2.56",
            "radius_secret": "radius-secret-" + secrets.token_hex(8),
        },
    )
    assert response.status_code == 201
    router_id = response.json()["id"]
    result = client.post(
        f"/api/v1/routers/{router_id}/user-manager/test-connection",
        headers=headers,
    )
    assert result.status_code == 409



def test_exact_user_inspection_endpoint_is_read_only_and_does_not_import(owner_client, monkeypatch):
    client, headers, _ = owner_client
    router_id = _create_router(client, headers)
    seen = {}

    def fake_inspect(**kwargs):
        seen.update(kwargs)
        return {
            "external_id": "*A1",
            "username": "voucher-100",
            "customer": "admin",
            "disabled": "false",
            "actual_profile": "basic",
            "shared_users": "1",
            "usage": {
                "uptime_used": "2h",
                "download_used_bytes": "12345",
                "upload_used_bytes": "678",
                "last_seen": None,
                "active_sessions": "0",
                "missing_fields_are_unknown": True,
            },
            "profile": None,
            "limitations": [],
            "warnings": [],
        }

    monkeypatch.setattr(user_manager, "inspect_user_manager_user", fake_inspect)
    response = client.post(
        f"/api/v1/routers/{router_id}/user-manager/inspect-user",
        headers=headers,
        json={"username": "voucher-100"},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["found"] is True
    assert data["read_only"] is True
    assert data["credentials_read"] is False
    assert data["imported"] is False
    assert data["user"]["external_id"] == "*A1"
    assert data["user"]["actual_profile"] == "basic"
    assert data["user"]["usage"]["download_used_bytes"] == "12345"
    assert data["user"]["usage"]["missing_fields_are_unknown"] is True
    assert seen["target_username"] == "voucher-100"
    assert seen["host"] == "192.0.2.55"


def test_exact_user_inspection_endpoint_validates_username(owner_client):
    client, headers, _ = owner_client
    router_id = _create_router(client, headers)
    response = client.post(
        f"/api/v1/routers/{router_id}/user-manager/inspect-user",
        headers=headers,
        json={"username": ""},
    )
    assert response.status_code == 422



def test_single_user_preview_is_persisted_without_credentials_or_import(owner_client, monkeypatch):
    client, headers, _ = owner_client
    router_id = _create_router(client, headers)

    def fake_inspect(**kwargs):
        return {
            "external_id": "*PREVIEW1",
            "username": "preview-voucher",
            "actual_profile": "basic",
            "usage": {"uptime_used": "1h", "download_used_bytes": "1024"},
            "profile": {"name": "basic"},
            "limitations": [],
            "warnings": [],
        }

    monkeypatch.setattr(user_manager, "inspect_user_manager_user", fake_inspect)
    response = client.post(
        f"/api/v1/routers/{router_id}/user-manager/preview-user",
        headers=headers,
        json={"username": "preview-voucher"},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["read_only"] is True
    assert data["imported"] is False
    assert data["credentials_read"] is False
    assert data["classification"] == "new"
    assert data["credential_mode"] is None
    assert data["credential_state"] == "unavailable"
    assert "password" not in response.text.lower()

    db = SessionLocal()
    try:
        run = db.get(UserManagerSyncRun, UUID(data["sync_run_id"]))
        preview = db.get(UserManagerImportPreview, data["preview_id"])
        assert run is not None
        assert preview is not None
        assert preview.username == "preview-voucher"
        assert preview.safe_snapshot["usage"]["download_used_bytes"] == "1024"
        assert preview.credential_state == "unavailable"
        assert preview.classification == "new"
    finally:
        db.close()
