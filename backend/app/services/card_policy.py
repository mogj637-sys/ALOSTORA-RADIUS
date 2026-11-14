from datetime import datetime, timedelta


def calculate_expiry(first_used_at: datetime, validity_period_seconds: int | None) -> datetime | None:
    """Validity is wall-clock time from first successful use; None means unlimited."""
    if validity_period_seconds is None:
        return None
    if validity_period_seconds <= 0:
        raise ValueError("validity_period_seconds must be positive or None")
    return first_used_at + timedelta(seconds=validity_period_seconds)


def resolve_first_use(
    existing_first_used_at: datetime | None,
    now: datetime,
    validity_period_seconds: int | None,
) -> tuple[datetime, datetime | None]:
    """Keep the original first-use timestamp on subsequent authentications."""
    first_used_at = existing_first_used_at or now
    return first_used_at, calculate_expiry(first_used_at, validity_period_seconds)


def total_consumed_bytes(upload_bytes: int, download_bytes: int) -> int:
    if upload_bytes < 0 or download_bytes < 0:
        raise ValueError("traffic counters cannot be negative")
    return upload_bytes + download_bytes


def is_expired(expires_at: datetime | None, now: datetime) -> bool:
    """An unset expiry is unlimited; expiry continues while disconnected."""
    return expires_at is not None and now >= expires_at
