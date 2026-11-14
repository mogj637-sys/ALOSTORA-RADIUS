import os
from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

password_hasher = PasswordHash.recommended()
JWT_ALGORITHM = "HS256"


def _secret_key() -> str:
    secret = os.getenv("APP_SECRET_KEY", "development-only-change-me")
    if len(secret) < 32:
        raise RuntimeError("APP_SECRET_KEY must contain at least 32 characters")
    if secret in {"development-only-change-me", "replace-with-a-long-random-secret-before-use"}:
        raise RuntimeError("Set a private APP_SECRET_KEY before using authentication")
    return secret


def hash_password(password: str) -> str:
    if len(password) < 12:
        raise ValueError("Password must be at least 12 characters")
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return password_hasher.verify(password, password_hash)


def create_access_token(subject: str, expires_minutes: int | None = None) -> str:
    minutes = expires_minutes or int(os.getenv("JWT_ACCESS_TOKEN_MINUTES", "30"))
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=minutes),
    }
    return jwt.encode(payload, _secret_key(), algorithm=JWT_ALGORITHM)
