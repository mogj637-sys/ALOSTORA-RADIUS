import os

from cryptography.fernet import Fernet, InvalidToken


class RouterSecretEncryptionNotConfigured(RuntimeError):
    pass


def _fernet() -> Fernet:
    key = os.getenv("ROUTER_SECRET_ENCRYPTION_KEY")
    if not key:
        raise RouterSecretEncryptionNotConfigured(
            "ROUTER_SECRET_ENCRYPTION_KEY must be configured before saving router secrets"
        )
    try:
        return Fernet(key.encode("utf-8"))
    except (ValueError, TypeError) as exc:
        raise RouterSecretEncryptionNotConfigured(
            "ROUTER_SECRET_ENCRYPTION_KEY is not a valid Fernet key"
        ) from exc


def encrypt_router_secret(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_router_secret(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Router secret could not be decrypted with the configured key") from exc
