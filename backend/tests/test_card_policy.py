from datetime import datetime, timedelta, timezone

import pytest

from app.services.card_policy import (
    calculate_expiry,
    is_expired,
    resolve_first_use,
    total_consumed_bytes,
)


def test_expiry_is_calculated_from_first_use():
    first = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    assert calculate_expiry(first, 5 * 24 * 60 * 60) == first + timedelta(days=5)


def test_unlimited_validity_has_no_expiry():
    first = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert calculate_expiry(first, None) is None


def test_first_use_is_not_reset_on_reauthentication():
    original = datetime(2026, 1, 1, tzinfo=timezone.utc)
    later = original + timedelta(days=2)
    first_used_at, expires_at = resolve_first_use(original, later, 5 * 86400)
    assert first_used_at == original
    assert expires_at == original + timedelta(days=5)


def test_expiry_passes_even_when_card_is_disconnected():
    expiry = datetime(2026, 1, 6, tzinfo=timezone.utc)
    assert is_expired(expiry, expiry + timedelta(seconds=1))


def test_unlimited_card_never_expires():
    now = datetime.now(timezone.utc)
    assert not is_expired(None, now)


def test_traffic_counts_upload_and_download():
    assert total_consumed_bytes(120, 300) == 420


def test_negative_traffic_counter_is_rejected():
    with pytest.raises(ValueError):
        total_consumed_bytes(-1, 20)
