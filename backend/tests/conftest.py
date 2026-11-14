import secrets

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.models.auth import AdminUser, Role
from app.security import hash_password


@pytest.fixture
def owner_client(monkeypatch):
    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY", Fernet.generate_key().decode("ascii"))
    monkeypatch.setenv("ROUTER_SECRET_ENCRYPTION_KEY", Fernet.generate_key().decode("ascii"))
    monkeypatch.setenv("RADIUS_INTERNAL_API_KEY", "ci-radius-internal-key-" + secrets.token_hex(24))
    username = "ci_owner_" + secrets.token_hex(4)
    password = "a-strong-ci-password-123"

    db = SessionLocal()
    role = db.query(Role).filter_by(code="owner").first()
    if role is None:
        role = Role(code="owner", name="System Owner")
        db.add(role)
        db.flush()

    user = AdminUser(
        username=username,
        display_name="CI Owner",
        password_hash=hash_password(password),
        is_active=True,
        roles=[role],
    )
    db.add(user)
    db.commit()
    user_id = user.id
    db.close()

    with TestClient(app) as client:
        login = client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
        )
        assert login.status_code == 200
        token = login.json()["access_token"]
        yield client, {"Authorization": f"Bearer {token}"}, username

    cleanup = SessionLocal()
    account = cleanup.get(AdminUser, user_id)
    if account is not None:
        account.roles = []
        cleanup.delete(account)
        cleanup.commit()
    cleanup.close()
