from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.services.radius_service import (
    _remaining_limits,
    _snapshot_rate_limit,
    _snapshot_shared_users,
)


def _card(
    *,
    plan_snapshot=None,
    used_seconds=0,
    upload_bytes=0,
    download_bytes=0,
    expires_at=None,
):
    return SimpleNamespace(
        plan_snapshot={} if plan_snapshot is None else plan_snapshot,
        used_seconds=used_seconds,
        upload_bytes=upload_bytes,
        download_bytes=download_bytes,
        expires_at=expires_at,
    )


def test_remaining_limits_subtracts_time_and_both_traffic_directions():
    card = _card(
        plan_snapshot={
            "session_time_limit_seconds": 1_000,
            "data_limit_bytes": 1_000,
        },
        used_seconds=300,
        upload_bytes=100,
        download_bytes=250,
    )

    assert _remaining_limits(card, datetime(2026, 11, 18, tzinfo=timezone.utc)) == (700, 650)


def test_remaining_limits_never_returns_negative_values():
    card = _card(
        plan_snapshot={
            "session_time_limit_seconds": 60,
            "data_limit_bytes": 100,
        },
        used_seconds=90,
        upload_bytes=70,
        download_bytes=50,
    )

    assert _remaining_limits(card, datetime(2026, 11, 18, tzinfo=timezone.utc)) == (0, 0)


def test_validity_deadline_caps_remaining_session_time():
    now = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)
    card = _card(
        plan_snapshot={
            "session_time_limit_seconds": 3_600,
            "data_limit_bytes": 1_000,
        },
        used_seconds=300,
        upload_bytes=200,
        download_bytes=100,
        expires_at=now + timedelta(seconds=120),
    )

    assert _remaining_limits(card, now) == (120, 700)


def test_validity_deadline_is_reported_when_session_time_is_unlimited():
    now = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)
    card = _card(
        plan_snapshot={"data_limit_bytes": 2_000},
        upload_bytes=250,
        download_bytes=250,
        expires_at=now + timedelta(seconds=75),
    )

    assert _remaining_limits(card, now) == (75, 1_500)


def test_expired_validity_has_zero_remaining_time():
    now = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)
    card = _card(
        plan_snapshot={"session_time_limit_seconds": 3_600},
        used_seconds=60,
        expires_at=now - timedelta(seconds=5),
    )

    assert _remaining_limits(card, now) == (0, None)


@pytest.mark.parametrize(
    ("snapshot", "expected"),
    [
        ({}, 1),
        ({"settings": {}}, None),
        ({"settings": {"shared_users": None}}, None),
        ({"settings": {"shared_users": ""}}, None),
        ({"settings": {"shared_users": " 3 "}}, 3),
        ({"settings": {"shared_users": 4}}, 4),
        ({"settings": {"shared_users": 0}}, 1),
        ({"settings": {"shared_users": -2}}, 1),
        ({"settings": {"shared_users": "invalid"}}, 1),
    ],
)
def test_shared_user_limit_matches_legacy_and_current_snapshots(snapshot, expected):
    assert _snapshot_shared_users(_card(plan_snapshot=snapshot)) == expected


def test_speed_profile_takes_precedence_over_rate_limits():
    card = _card(
        plan_snapshot={
            "speed_profile": "premium-4m",
            "settings": {"rate_limit_rx": 2048, "rate_limit_tx": 4096},
        }
    )

    assert _snapshot_rate_limit(card) == "premium-4m"


def test_speed_is_derived_from_complete_rate_limits_when_profile_is_absent():
    card = _card(
        plan_snapshot={
            "settings": {
                "rate_limit_rx": 2,
                "rate_limit_tx": 4,
                "rate_limit_unit": "Mbps",
            }
        }
    )

    assert _snapshot_rate_limit(card) == "2Mbps/4Mbps"


def test_speed_is_unknown_when_rate_limits_are_incomplete():
    card = _card(plan_snapshot={"settings": {"rate_limit_rx": 2}})

    assert _snapshot_rate_limit(card) is None
