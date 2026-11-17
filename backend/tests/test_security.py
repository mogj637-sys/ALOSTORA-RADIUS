import jwt
import pytest

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



@pytest.mark.parametrize(
    "secret",
    [
        None,
        "development-only-change-me",
        "replace-with-a-long-random-secret-before-use",
    ],
)
def test_authentication_rejects_tokens_when_jwt_secret_is_missing_or_placeholder(
    monkeypatch, secret
):
    from datetime import datetime, timedelta, timezone

    from fastapi import HTTPException
    from fastapi.security import HTTPAuthorizationCredentials

    from app.api.deps import get_current_user

    if secret is None:
        monkeypatch.delenv("APP_SECRET_KEY", raising=False)
        signing_secret = "development-only-change-me"
    else:
        monkeypatch.setenv("APP_SECRET_KEY", secret)
        signing_secret = secret

    forged_token = jwt.encode(
        {
            "sub": "1",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        signing_secret,
        algorithm="HS256",
    )
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=forged_token,
    )

    with pytest.raises(HTTPException) as error:
        get_current_user(credentials=credentials, db=None)

    assert error.value.status_code == 503
