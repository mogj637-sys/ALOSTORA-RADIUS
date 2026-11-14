import os
import secrets
from types import SimpleNamespace
from uuid import UUID

from pyrad import packet
from pyrad.client import Timeout

from app.db.session import SessionLocal
from app.models.core import Card, RadiusSession, Router
from app.services.router_secrets import decrypt_router_secret
from app.services.radius_disconnect import send_disconnect_for_session


def _active_session(owner_client):
    client, headers, _ = owner_client
    router = client.post(
        "/api/v1/routers",
        headers=headers,
        json={
            "name": "CoA test router",
            "nas_identifier": "coa-nas-" + secrets.token_hex(4),
            "management_host": "192.0.2.60",
            "radius_client_address": "192.0.2.60/32",
            "radius_secret": "coa-shared-secret-" + secrets.token_hex(6),
        },
    )
    assert router.status_code == 201, router.text

    plan = client.post(
        "/api/v1/plans",
        headers=headers,
        json={
            "code": "COA-" + secrets.token_hex(4).upper(),
            "name": "CoA plan",
            "price": "10.00",
            "session_time_limit_seconds": 300,
            "data_limit_bytes": 10000,
        },
    )
    assert plan.status_code == 201, plan.text

    card = client.post(
        "/api/v1/cards/single",
        headers=headers,
        json={
            "plan_id": plan.json()["id"],
            "username": "COA" + secrets.token_hex(5).upper(),
            "card_type": "separate_credentials",
            "password": "coa-test-password",
        },
    )
    assert card.status_code == 201, card.text

    internal = {"X-Radius-Internal-Key": os.environ["RADIUS_INTERNAL_API_KEY"]}
    auth = client.post(
        "/internal/radius/authorize",
        headers=internal,
        json={
            "nas_identifier": router.json()["nas_identifier"],
            "username": card.json()["username"],
            "password": "coa-test-password",
        },
    )
    assert auth.status_code == 200, auth.text

    started = client.post(
        "/internal/radius/accounting",
        headers=internal,
        json={
            "nas_identifier": router.json()["nas_identifier"],
            "username": card.json()["username"],
            "acct_session_id": "coa-session-" + secrets.token_hex(5),
            "status_type": "Start",
        },
    )
    assert started.status_code == 200, started.text

    db = SessionLocal()
    session = db.query(RadiusSession).filter_by(card_id=UUID(card.json()["id"])).one()
    return db, session


def test_disconnect_sender_builds_signed_disconnect_request(monkeypatch, owner_client):
    monkeypatch.setenv("RADIUS_COA_ENABLED", "true")
    monkeypatch.setenv("RADIUS_COA_PORT", "1700")
    db, session = _active_session(owner_client)
    created = {}

    class FakeClient:
        def __init__(self, **kwargs):
            created["client_kwargs"] = kwargs

        def CreateCoAPacket(self, **kwargs):
            created["packet_kwargs"] = kwargs
            return kwargs

        def SendPacket(self, request):
            created["request"] = request
            return SimpleNamespace(code=packet.DisconnectACK)

    monkeypatch.setattr("app.services.radius_disconnect.Client", FakeClient)
    monkeypatch.setattr("app.services.radius_disconnect.Dictionary", lambda path: path)

    try:
        assert send_disconnect_for_session(db, session) is True
        assert created["client_kwargs"]["server"] == "192.0.2.60"
        assert created["client_kwargs"]["coaport"] == 1700
        assert created["packet_kwargs"]["code"] == packet.DisconnectRequest
        assert created["packet_kwargs"]["message_authenticator"] is True
        card = db.get(Card, session.card_id)
        router = db.get(Router, session.router_id)
        assert created["packet_kwargs"]["Acct_Session_Id"] == session.acct_session_id
        assert created["packet_kwargs"]["User_Name"] == card.username
        assert created["packet_kwargs"]["NAS_Identifier"] == router.nas_identifier
        assert created["client_kwargs"]["secret"] == decrypt_router_secret(router.radius_secret_encrypted).encode("utf-8")
    finally:
        db.close()


def test_disconnect_sender_returns_none_when_disabled(monkeypatch, owner_client):
    monkeypatch.setenv("RADIUS_COA_ENABLED", "false")
    db, session = _active_session(owner_client)
    try:
        assert send_disconnect_for_session(db, session) is None
    finally:
        db.close()


def test_disconnect_sender_reports_timeout(monkeypatch, owner_client):
    monkeypatch.setenv("RADIUS_COA_ENABLED", "true")
    db, session = _active_session(owner_client)

    class TimeoutClient:
        def __init__(self, **kwargs):
            pass

        def CreateCoAPacket(self, **kwargs):
            return kwargs

        def SendPacket(self, request):
            raise Timeout()

    monkeypatch.setattr("app.services.radius_disconnect.Client", TimeoutClient)
    monkeypatch.setattr("app.services.radius_disconnect.Dictionary", lambda path: path)

    try:
        assert send_disconnect_for_session(db, session) is False
    finally:
        db.close()


def test_admin_suspend_sends_disconnect_for_active_card(monkeypatch, owner_client):
    import os

    monkeypatch.setenv("RADIUS_COA_ENABLED", "true")
    monkeypatch.setattr("app.api.cards.send_disconnect_for_session", lambda db, session: True)
    client, headers, _ = owner_client
    db, session = _active_session(owner_client)
    try:
        suspended = client.patch(
            f"/api/v1/cards/{session.card_id}/status",
            headers=headers,
            json={"action": "suspend"},
        )
        assert suspended.status_code == 200, suspended.text
        event = (
            db.query(__import__("app.models.core", fromlist=["CardEvent"]).CardEvent)
            .filter_by(card_id=session.card_id, event_type="radius_disconnect_sent")
            .one()
        )
        assert event.actor
    finally:
        db.close()
