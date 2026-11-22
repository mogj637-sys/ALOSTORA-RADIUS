import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.api.deps import get_current_user
from app.security import create_access_token, hash_password, verify_password


def test_password_hash_round_trip():
    password = "a-long-local-test-password"
    encoded = hash_password(password)
    assert encoded != password
    assert verify_password(password, encoded)
    assert not verify_password("incorrect-password", encoded)


def test_short_password_is_rejected():
    with pytest.raises(ValueError):
        hash_password("short")


def test_access_token_contains_subject_and_expiry(monkeypatch):
    secret = "test-only-secret-key-with-more-than-thirty-two-characters"
    monkeypatch.setenv("APP_SECRET_KEY", secret)
    token = create_access_token("42", expires_minutes=5)
    payload = jwt.decode(token, secret, algorithms=["HS256"])
    assert payload["sub"] == "42"
    assert "exp" in payload


def test_placeholder_jwt_secret_is_rejected(monkeypatch):
    monkeypatch.setenv("APP_SECRET_KEY", "replace-with-a-long-random-secret-before-use")
    with pytest.raises(RuntimeError):
        create_access_token("42")


def test_auth_dependency_rejects_placeholder_signing_secret(monkeypatch):
    monkeypatch.setenv("APP_SECRET_KEY", "development-only-change-me")
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="forged-placeholder-token",
    )

    with pytest.raises(HTTPException) as exc:
        get_current_user(credentials=credentials, db=None)

    assert exc.value.status_code == 503
