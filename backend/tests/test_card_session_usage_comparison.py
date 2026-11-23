from datetime import datetime, timezone
from types import SimpleNamespace

from app.api.cards import (
    _card_session_activity_summary,
    _card_session_usage_comparison,
    _card_session_usage_comparison_totals,
)


def _session(upload: int, download: int, seconds: int):
    return SimpleNamespace(
        input_octets=upload,
        output_octets=download,
        session_time_seconds=seconds,
    )


def test_card_usage_matches_sum_of_radius_sessions():
    card = SimpleNamespace(upload_bytes=350, download_bytes=900, used_seconds=420)
    sessions = [
        _session(upload=100, download=300, seconds=120),
        _session(upload=250, download=600, seconds=300),
    ]

    result = _card_session_usage_comparison(card, sessions)

    assert result == {
        "card": {"upload_bytes": 350, "download_bytes": 900, "used_seconds": 420},
        "sessions": {"upload_bytes": 350, "download_bytes": 900, "used_seconds": 420},
        "difference": {"upload_bytes": 0, "download_bytes": 0, "used_seconds": 0},
        "is_consistent": True,
    }


def test_card_usage_reports_signed_differences_from_session_history():
    card = SimpleNamespace(upload_bytes=500, download_bytes=700, used_seconds=600)
    sessions = [
        _session(upload=450, download=750, seconds=540),
    ]

    result = _card_session_usage_comparison(card, sessions)

    assert result["difference"] == {
        "upload_bytes": 50,
        "download_bytes": -50,
        "used_seconds": 60,
    }
    assert result["is_consistent"] is False


def test_card_usage_with_no_sessions_compares_against_zero_totals():
    card = SimpleNamespace(upload_bytes=0, download_bytes=0, used_seconds=0)

    result = _card_session_usage_comparison(card, [])

    assert result["sessions"] == {
        "upload_bytes": 0,
        "download_bytes": 0,
        "used_seconds": 0,
    }
    assert result["is_consistent"] is True


def test_card_usage_comparison_accepts_database_aggregate_totals():
    card = SimpleNamespace(upload_bytes=900, download_bytes=1400, used_seconds=720)
    result = _card_session_usage_comparison_totals(
        card,
        {"upload_bytes": 850, "download_bytes": 1400, "used_seconds": 600},
    )

    assert result["sessions"] == {
        "upload_bytes": 850,
        "download_bytes": 1400,
        "used_seconds": 600,
    }
    assert result["difference"] == {
        "upload_bytes": 50,
        "download_bytes": 0,
        "used_seconds": 120,
    }
    assert result["is_consistent"] is False


def test_card_usage_comparison_normalizes_empty_database_aggregates():
    card = SimpleNamespace(upload_bytes=0, download_bytes=0, used_seconds=0)
    result = _card_session_usage_comparison_totals(
        card,
        {"upload_bytes": None, "download_bytes": None, "used_seconds": None},
    )

    assert result["sessions"] == {
        "upload_bytes": 0,
        "download_bytes": 0,
        "used_seconds": 0,
    }
    assert result["is_consistent"] is True


def test_card_session_activity_summary_reports_active_ended_and_latest_timestamps():
    last_session = datetime(2026, 11, 23, 10, 30, tzinfo=timezone.utc)
    last_accounting = datetime(2026, 11, 23, 10, 32, tzinfo=timezone.utc)

    result = _card_session_activity_summary(7, 2, last_session, last_accounting)

    assert result == {
        "total_sessions_count": 7,
        "active_sessions_count": 2,
        "ended_sessions_count": 5,
        "last_session_at": last_session,
        "last_accounting_at": last_accounting,
    }


def test_card_session_activity_summary_defaults_cards_without_sessions_to_empty():
    assert _card_session_activity_summary(0, 0, None, None) == {
        "total_sessions_count": 0,
        "active_sessions_count": 0,
        "ended_sessions_count": 0,
        "last_session_at": None,
        "last_accounting_at": None,
    }
