import os

from cryptography.fernet import Fernet, InvalidToken


class CredentialEncryptionNotConfigured(RuntimeError):
    pass


def _fernet() -> Fernet:
    key = os.getenv("CREDENTIAL_ENCRYPTION_KEY")
    if not key:
        raise CredentialEncryptionNotConfigured(
            "CREDENTIAL_ENCRYPTION_KEY must be configured before creating cards"
        )
    try:
        return Fernet(key.encode("utf-8"))
    except (ValueError, TypeError) as exc:
        raise CredentialEncryptionNotConfigured(
            "CREDENTIAL_ENCRYPTION_KEY is not a valid Fernet key"
        ) from exc


def encrypt_credential(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_credential(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Credential could not be decrypted with the configured key") from exc
