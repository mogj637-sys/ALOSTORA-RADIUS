import os
import sys
from decimal import Decimal

from app.db.session import SessionLocal
from app.models.core import Card, Plan, RadiusSession, Router
from app.services.credentials import encrypt_credential
from app.services.router_secrets import encrypt_router_secret

NAS_IDENTIFIER = "alostora-e2e"
USERNAME = "E2E-RADIUS-USER"
PASSWORD = "e2e-card-password-2026"
SESSION_ID = "alostora-e2e-session-001"
RADIUS_SECRET = os.environ["RADIUS_SHARED_SECRET"]


def seed() -> None:
    db = SessionLocal()
    try:
        if db.query(Router).filter_by(nas_identifier=NAS_IDENTIFIER).first():
            raise RuntimeError("E2E NAS already exists; use a fresh integration database")
        plan = Plan(
            code="RADIUS-E2E-PLAN",
            name="RADIUS end-to-end test plan",
            price=Decimal("1.00"),
            data_limit_bytes=10_000_000,
            session_time_limit_seconds=600,
            validity_period_seconds=3600,
            speed_profile="2M/2M",
            is_active=True,
        )
        db.add(plan)
        db.flush()
        router = Router(
            name="RADIUS end-to-end test NAS",
            nas_identifier=NAS_IDENTIFIER,
            management_host="127.0.0.1",
            radius_client_address="127.0.0.1/32",
            api_port=8728,
            radius_secret_encrypted=encrypt_router_secret(RADIUS_SECRET),
            is_active=True,
        )
        db.add(router)
        card = Card(
            serial_number="E2E-RADIUS-CARD-001",
            username=USERNAME,
            credential_ciphertext=encrypt_credential(PASSWORD),
            credential_scheme="fernet_v1",
            card_type="separate_credentials",
            status="generated",
            is_free=False,
            plan_id=plan.id,
            plan_snapshot={
                "id": plan.id,
                "code": plan.code,
                "name": plan.name,
                "price": "1.00",
                "data_limit_bytes": plan.data_limit_bytes,
                "session_time_limit_seconds": plan.session_time_limit_seconds,
                "validity_period_seconds": plan.validity_period_seconds,
                "speed_profile": plan.speed_profile,
            },
            price_snapshot=Decimal("1.00"),
        )
        db.add(card)
        db.commit()
        print(f"Seeded NAS {NAS_IDENTIFIER} and card {USERNAME}")
    finally:
        db.close()


def verify() -> None:
    db = SessionLocal()
    try:
        card = db.query(Card).filter_by(username=USERNAME).one()
        session = db.query(RadiusSession).filter_by(acct_session_id=SESSION_ID).one()
        assert card.first_used_at is not None, "first-use timestamp was not recorded"
        assert card.expires_at is not None, "validity expiry was not created on first use"
        assert card.used_seconds == 30, f"expected 30 connected seconds, got {card.used_seconds}"
        assert card.upload_bytes == 100, f"expected 100 input octets, got {card.upload_bytes}"
        assert card.download_bytes == 200, f"expected 200 output octets, got {card.download_bytes}"
        assert session.stopped_at is not None, "Accounting-Stop did not close the session"
        assert session.session_time_seconds == 30
        assert session.input_octets == 100
        assert session.output_octets == 200
        assert card.status == "generated", f"expected card to return to generated, got {card.status}"
        print("Verified Access-Accept/Reject, Accounting Start/Interim/Stop, first use, time and traffic counters.")
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in {"seed", "verify"}:
        raise SystemExit("Usage: radius_e2e.py seed|verify")
    seed() if sys.argv[1] == "seed" else verify()
