from cryptography.fernet import Fernet

from app.services.credentials import decrypt_credential, encrypt_credential


def test_credential_is_encrypted_and_can_be_decrypted(monkeypatch):
    key = Fernet.generate_key().decode("ascii")
    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY", key)
    encrypted = encrypt_credential("voucher-password")
    assert encrypted != "voucher-password"
    assert decrypt_credential(encrypted) == "voucher-password"


def test_empty_password_can_be_encrypted_for_username_only_cards(monkeypatch):
    key = Fernet.generate_key().decode("ascii")
    monkeypatch.setenv("CREDENTIAL_ENCRYPTION_KEY", key)
    assert decrypt_credential(encrypt_credential("")) == ""
