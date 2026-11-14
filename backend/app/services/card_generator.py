import secrets
import string


CHARSETS = {
    "digits": string.digits,
    "letters": string.ascii_uppercase,
    "alphanumeric": string.ascii_uppercase + string.digits,
}


def generate_username(length: int, mode: str, prefix: str = "") -> str:
    if mode not in CHARSETS:
        raise ValueError("Unsupported username generation mode")
    if length < 3 or length > 32:
        raise ValueError("Username length must be between 3 and 32")
    if len(prefix) >= length:
        raise ValueError("Prefix must be shorter than the requested username")
    if prefix and not prefix.isalnum():
        raise ValueError("Prefix must contain only letters and numbers")
    charset = CHARSETS[mode]
    suffix_length = length - len(prefix)
    return prefix + "".join(secrets.choice(charset) for _ in range(suffix_length))


def generate_password(length: int = 10) -> str:
    if length < 4 or length > 32:
        raise ValueError("Password length must be between 4 and 32")
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))
