import os
import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from app.db.session import SessionLocal
from app.models.core import Card, RadiusSession, Router


def _router(client, headers):
    response = client.post(
        "/api/v1/routers",
        headers=headers,
        json={
            "name": "RADIUS test router",
            "nas_identifier": "radius-nas-" + secrets.token_hex(4),
            "management_host": "192.0.2.50",
            "radius_secret": "radius-shared-" + secrets.token_hex(8),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _card(client, headers, *, time_limit=300, data_limit=2000, validity=3600):
    code = "RAD-" + secrets.token_hex(4).upper()
    plan = client.post(
        "/api/v1/plans",
        headers=headers,
        json={
            "code": code,
            "name": "RADIUS test plan",
            "price": "10.00",
            "session_time_limit_seconds": time_limit,
            "data_limit_bytes": data_limit,
            "validity_period_seconds": validity,
            "speed_profile": "2M/2M",
        },
    )
    assert plan.status_code == 201, plan.text
    username = "RAD" + secrets.token_hex(5).upper()
    password = "radius-password-" + secrets.token_hex(4)
    created = client.post(
        "/api/v1/cards/single",
        headers=headers,
        json={
            "plan_id": plan.json()["id"],
            "username": username,
            "card_type": "separate_credentials",
            "password": password,
        },
    )
    assert created.status_code == 201, created.text
    return created.json(), password


def _radius_headers():
    return {"X-Radius-Internal-Key": os.environ["RADIUS_INTERNAL_API_KEY"]}


def test_radius_authorize_starts_first_use_and_returns_mikrotik_limits(owner_client):
    client, headers, _ = owner_client
    router = _router(client, headers)
    card, password = _card(client, headers)

    accepted = client.post(
        "/internal/radius/authorize",
        headers=_radius_headers(),
        json={
            "nas_identifier": router["nas_identifier"],
            "username": card["username"],
            "password": password,
            "framed_ip_address": "10.10.10.20",
            "calling_station_id": "AA:BB:CC:DD:EE:FF",
        },
    )
    assert accepted.status_code == 200, accepted.text
    result = accepted.json()
    assert result["accepted"] is True
    assert result["reply"]["Port-Limit"] == 1
    assert result["reply"]["Acct-Interim-Interval"] == 60
    assert result["reply"]["Session-Timeout"] == 300
    assert result["reply"]["Mikrotik-Total-Limit"] == 2000
    assert result["reply"]["Mikrotik-Rate-Limit"] == "2M/2M"

    db = SessionLocal()
    saved = db.get(Card, UUID(card["id"]))
    assert saved.first_used_at is not None
    assert saved.expires_at is not None
    assert saved.radius_auth_reserved_until is not None
    db.close()

    second = client.post(
        "/internal/radius/authorize",
        headers=_radius_headers(),
        json={
            "nas_identifier": router["nas_identifier"],
            "username": card["username"],
            "password": password,
        },
    )
    assert second.status_code == 401
    assert second.json()["accepted"] is False
    assert "طلب دخول آخر" in second.json()["reason"]


def test_radius_accounting_is_idempotent_and_counts_connected_time_and_both_directions(owner_client):
    client, headers, _ = owner_client
    router = _router(client, headers)
    card, password = _card(client, headers)
    internal_headers = _radius_headers()

    auth = client.post(
        "/internal/radius/authorize",
        headers=internal_headers,
        json={"nas_identifier": router["nas_identifier"], "username": card["username"], "password": password},
    )
    assert auth.json()["accepted"] is True

    start_time = datetime.now(timezone.utc)
    base = {
        "nas_identifier": router["nas_identifier"],
        "username": card["username"],
        "acct_session_id": "session-" + secrets.token_hex(6),
        "event_timestamp": start_time.isoformat(),
        "framed_ip_address": "10.10.10.21",
        "calling_station_id": "11:22:33:44:55:66",
    }
    started = client.post(
        "/internal/radius/accounting",
        headers=internal_headers,
        json={**base, "status_type": "Start"},
    )
    assert started.status_code == 200, started.text
    assert started.json()["processed"] is True

    second_auth = client.post(
        "/internal/radius/authorize",
        headers=internal_headers,
        json={"nas_identifier": router["nas_identifier"], "username": card["username"], "password": password},
    )
    assert second_auth.json()["accepted"] is False

    interim = {
        **base,
        "status_type": "Interim-Update",
        "event_timestamp": (start_time + timedelta(seconds=60)).isoformat(),
        "session_time_seconds": 60,
        "input_octets": 300,
        "output_octets": 400,
    }
    first_interim = client.post("/internal/radius/accounting", headers=internal_headers, json=interim)
    assert first_interim.status_code == 200
    assert first_interim.json()["processed"] is True
    repeated_interim = client.post("/internal/radius/accounting", headers=internal_headers, json=interim)
    assert repeated_interim.status_code == 200
    assert repeated_interim.json()["duplicate"] is True

    stopped = client.post(
        "/internal/radius/accounting",
        headers=internal_headers,
        json={
            **base,
            "status_type": "Stop",
            "event_timestamp": (start_time + timedelta(seconds=120)).isoformat(),
            "session_time_seconds": 120,
            "input_octets": 600,
            "output_octets": 800,
        },
    )
    assert stopped.status_code == 200, stopped.text
    assert stopped.json()["processed"] is True

    db = SessionLocal()
    saved = db.get(Card, UUID(card["id"]))
    assert saved.used_seconds == 120
    assert saved.upload_bytes == 600
    assert saved.download_bytes == 800
    assert saved.status == "generated"
    session = db.query(RadiusSession).filter_by(acct_session_id=base["acct_session_id"]).one()
    assert session.stopped_at is not None
    assert session.session_time_seconds == 120
    db.close()


def test_radius_accounting_requests_disconnect_when_time_or_data_is_exhausted(owner_client):
    client, headers, _ = owner_client
    router = _router(client, headers)
    card, password = _card(client, headers, time_limit=60, data_limit=1000, validity=3600)
    internal_headers = _radius_headers()
    auth = client.post(
        "/internal/radius/authorize",
        headers=internal_headers,
        json={"nas_identifier": router["nas_identifier"], "username": card["username"], "password": password},
    )
    assert auth.json()["accepted"] is True

    now = datetime.now(timezone.utc)
    base = {
        "nas_identifier": router["nas_identifier"],
        "username": card["username"],
        "acct_session_id": "limit-" + secrets.token_hex(6),
        "event_timestamp": now.isoformat(),
    }
    start = client.post(
        "/internal/radius/accounting",
        headers=internal_headers,
        json={**base, "status_type": "Start"},
    )
    assert start.json()["processed"] is True

    interim = client.post(
        "/internal/radius/accounting",
        headers=internal_headers,
        json={
            **base,
            "status_type": "Interim-Update",
            "event_timestamp": (now + timedelta(seconds=60)).isoformat(),
            "session_time_seconds": 60,
            "input_octets": 500,
            "output_octets": 500,
        },
    )
    assert interim.status_code == 200
    assert interim.json()["disconnect_required"] is True

    db = SessionLocal()
    saved = db.get(Card, UUID(card["id"]))
    assert saved.status == "exhausted"
    assert saved.used_seconds == 60
    assert saved.upload_bytes + saved.download_bytes == 1000
    db.close()


def test_radius_internal_endpoints_reject_missing_or_invalid_shared_key(owner_client):
    client, _, _ = owner_client
    payload = {
        "nas_identifier": "unknown",
        "username": "unknown",
        "password": "x",
    }
    missing = client.post("/internal/radius/authorize", json=payload)
    assert missing.status_code == 401
    invalid = client.post(
        "/internal/radius/authorize",
        headers={"X-Radius-Internal-Key": "not-the-key"},
        json=payload,
    )
    assert invalid.status_code == 401


def test_accounting_supports_gigawords_and_closes_sessions_after_router_deactivation(owner_client):
    client, headers, _ = owner_client
    router = _router(client, headers)
    card, password = _card(client, headers, data_limit=10**12)
    internal_headers = _radius_headers()
    auth = client.post(
        "/internal/radius/authorize",
        headers=internal_headers,
        json={"nas_identifier": router["nas_identifier"], "username": card["username"], "password": password},
    )
    assert auth.json()["accepted"] is True

    now = datetime.now(timezone.utc)
    base = {
        "nas_identifier": router["nas_identifier"],
        "username": card["username"],
        "acct_session_id": "gigawords-" + secrets.token_hex(6),
        "event_timestamp": now.isoformat(),
    }
    started = client.post(
        "/internal/radius/accounting",
        headers=internal_headers,
        json={**base, "status_type": "Start"},
    )
    assert started.json()["processed"] is True

    deactivated = client.patch(
        f"/api/v1/routers/{router['id']}",
        headers=headers,
        json={"is_active": False},
    )
    assert deactivated.status_code == 200

    interim = client.post(
        "/internal/radius/accounting",
        headers=internal_headers,
        json={
            **base,
            "status_type": "Interim-Update",
            "event_timestamp": (now + timedelta(seconds=30)).isoformat(),
            "session_time_seconds": 30,
            "input_octets": 10,
            "input_gigawords": 1,
            "output_octets": 20,
        },
    )
    assert interim.status_code == 200
    assert interim.json()["processed"] is True
    assert interim.json()["disconnect_required"] is True

    stopped = client.post(
        "/internal/radius/accounting",
        headers=internal_headers,
        json={
            **base,
            "status_type": "Stop",
            "event_timestamp": (now + timedelta(seconds=40)).isoformat(),
            "session_time_seconds": 40,
            "input_octets": 15,
            "input_gigawords": 1,
            "output_octets": 30,
        },
    )
    assert stopped.status_code == 200
    assert stopped.json()["processed"] is True

    db = SessionLocal()
    saved = db.get(Card, UUID(card["id"]))
    assert saved.upload_bytes == (2**32) + 15
    assert saved.download_bytes == 30
    assert saved.used_seconds == 40
    assert saved.status == "exhausted"
    session = db.query(RadiusSession).filter_by(acct_session_id=base["acct_session_id"]).one()
    assert session.stopped_at is not None
    db.close()

    new_start = client.post(
        "/internal/radius/accounting",
        headers=internal_headers,
        json={
            **base,
            "acct_session_id": "disabled-" + secrets.token_hex(5),
            "status_type": "Start",
        },
    )
    assert new_start.status_code == 409
    assert new_start.json()["processed"] is False


def test_radius_rejects_wrong_password_without_starting_first_use(owner_client):
    client, headers, _ = owner_client
    router = _router(client, headers)
    card, _ = _card(client, headers)
    response = client.post(
        "/internal/radius/authorize",
        headers=_radius_headers(),
        json={
            "nas_identifier": router["nas_identifier"],
            "username": card["username"],
            "password": "definitely-the-wrong-password",
        },
    )
    assert response.status_code == 401
    assert response.json()["accepted"] is False

    db = SessionLocal()
    saved = db.get(Card, UUID(card["id"]))
    assert saved.first_used_at is None
    assert saved.expires_at is None
    assert saved.radius_auth_reserved_until is None
    db.close()


def test_radius_accounting_handles_gigawords_and_out_of_order_packets(owner_client):
    client, headers, _ = owner_client
    router = _router(client, headers)
    card, password = _card(client, headers, time_limit=None, data_limit=None, validity=None)
    internal_headers = _radius_headers()
    auth = client.post(
        "/internal/radius/authorize",
        headers=internal_headers,
        json={"nas_identifier": router["nas_identifier"], "username": card["username"], "password": password},
    )
    assert auth.status_code == 200

    started_at = datetime.now(timezone.utc)
    base = {
        "nas_identifier": router["nas_identifier"],
        "username": card["username"],
        "acct_session_id": "wide-" + secrets.token_hex(6),
    }
    started = client.post(
        "/internal/radius/accounting",
        headers=internal_headers,
        json={**base, "status_type": "Start", "event_timestamp": started_at.isoformat()},
    )
    assert started.status_code == 200

    latest = {
        **base,
        "status_type": "Interim-Update",
        "event_timestamp": (started_at + timedelta(seconds=60)).isoformat(),
        "session_time_seconds": 60,
        "input_octets": 10,
        "output_octets": 20,
        "input_gigawords": 1,
        "output_gigawords": 2,
    }
    first = client.post("/internal/radius/accounting", headers=internal_headers, json=latest)
    assert first.status_code == 200

    older = {
        **base,
        "status_type": "Interim-Update",
        "event_timestamp": (started_at + timedelta(seconds=30)).isoformat(),
        "session_time_seconds": 30,
        "input_octets": 5,
        "output_octets": 10,
    }
    out_of_order = client.post("/internal/radius/accounting", headers=internal_headers, json=older)
    assert out_of_order.status_code == 200

    db = SessionLocal()
    saved = db.get(Card, UUID(card["id"]))
    assert saved.upload_bytes == (2**32) + 10
    assert saved.download_bytes == (2 * (2**32)) + 20
    assert saved.used_seconds == 60
    db.close()


def test_validity_expiry_continues_after_disconnect(owner_client):
    client, headers, _ = owner_client
    router = _router(client, headers)
    card, password = _card(client, headers, time_limit=None, data_limit=None, validity=1)
    internal_headers = _radius_headers()
    auth = client.post(
        "/internal/radius/authorize",
        headers=internal_headers,
        json={"nas_identifier": router["nas_identifier"], "username": card["username"], "password": password},
    )
    assert auth.status_code == 200

    started_at = datetime.now(timezone.utc)
    base = {
        "nas_identifier": router["nas_identifier"],
        "username": card["username"],
        "acct_session_id": "expiry-" + secrets.token_hex(6),
    }
    started = client.post(
        "/internal/radius/accounting",
        headers=internal_headers,
        json={**base, "status_type": "Start", "event_timestamp": started_at.isoformat()},
    )
    assert started.status_code == 200
    stopped = client.post(
        "/internal/radius/accounting",
        headers=internal_headers,
        json={
            **base,
            "status_type": "Stop",
            "event_timestamp": (started_at + timedelta(seconds=3)).isoformat(),
            "session_time_seconds": 1,
        },
    )
    assert stopped.status_code == 200

    db = SessionLocal()
    saved = db.get(Card, UUID(card["id"]))
    assert saved.status == "expired"
    assert saved.used_seconds == 1
    db.close()
