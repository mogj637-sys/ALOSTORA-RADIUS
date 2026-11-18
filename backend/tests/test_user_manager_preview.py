import copy

from app.services.user_manager_preview import build_user_manager_preview


def test_preview_classifies_new_linked_conflict_and_missing_identity():
    records = [
        {"external_id": "*1", "username": "new-card", "actual_profile": "basic"},
        {"external_id": "*2", "username": "linked-card"},
        {"external_id": "*3", "username": "existing-name"},
        {"username": "no-id"},
    ]
    result = build_user_manager_preview(
        records,
        existing_cards_by_username={"existing-name": "card-3"},
        source_links_by_external_id={"*2": "card-2"},
    )

    assert [row["classification"] for row in result] == [
        "new", "already_linked", "username_conflict", "invalid"
    ]
    assert result[1]["matched_card_id"] == "card-2"
    assert result[2]["matched_card_id"] == "card-3"
    assert result[3]["issues"]


def test_preview_is_deterministic_and_does_not_mutate_source():
    source = {
        "external_id": "*9",
        "username": "voucher-9",
        "usage": {"download_used_bytes": "100"},
        "password": "must-not-leak",
    }
    original = copy.deepcopy(source)

    first = build_user_manager_preview([source])[0]
    second = build_user_manager_preview([source])[0]

    assert source == original
    assert first["source_fingerprint"] == second["source_fingerprint"]
    assert "password" not in first["safe_snapshot"]
    assert first["credential_mode"] == "separate_credentials"
    assert first["credential_state"] == "plaintext_available"
    assert "must-not-leak" not in repr(first)


def test_preview_strips_nested_secrets_and_detects_batch_duplicates():
    records = [
        {"external_id": "*A", "username": "one", "auth": {"password": "x", "method": "pap"}},
        {"external_id": "*A", "username": "two"},
    ]
    result = build_user_manager_preview(records)

    assert result[0]["classification"] == "new"
    assert result[0]["safe_snapshot"]["auth"] == {"method": "pap"}
    assert result[1]["classification"] == "duplicate_in_batch"


def test_preview_detects_all_three_credential_modes_without_exposing_passwords():
    records = [
        {"external_id": "1", "username": "only", "password": ""},
        {"external_id": "2", "username": "same", "password": "same"},
        {"external_id": "3", "username": "different", "password": "secret-value"},
    ]

    result = build_user_manager_preview(records)

    assert [row["credential_mode"] for row in result] == [
        "username_only", "same_credentials", "separate_credentials"
    ]
    assert all(row["credential_state"] == "plaintext_available" for row in result)
    assert "password" not in result[2]["safe_snapshot"]
    assert "secret-value" not in repr(result)


def test_preview_does_not_assume_username_only_when_password_field_is_missing():
    result = build_user_manager_preview([
        {"external_id": "1", "username": "unknown"},
        {"external_id": "2", "username": "hashed", "password-hash": "abc123"},
    ])

    assert result[0]["credential_mode"] is None
    assert result[0]["credential_state"] == "unavailable"
    assert result[1]["credential_mode"] is None
    assert result[1]["credential_state"] == "verifier_unverified"


def test_preview_strips_routeros_secret_aliases():
    result = build_user_manager_preview([{
        "external_id": "1",
        "username": "safe",
        "api-secret": "router-secret",
        "user-password": "card-secret",
        "normal-field": "keep",
    }])[0]

    assert result["safe_snapshot"] == {
        "external_id": "1", "username": "safe", "normal-field": "keep"
    }
    assert "router-secret" not in repr(result)
    assert "card-secret" not in repr(result)


def test_preview_rejects_non_object_record():
    try:
        build_user_manager_preview(["not-a-record"])
    except ValueError as exc:
        assert "كائن بيانات" in str(exc)
    else:
        raise AssertionError("Expected ValueError")



def test_preview_fingerprint_tracks_credential_availability_without_storing_secret():
    unavailable = build_user_manager_preview([{
        "external_id": "*10", "username": "credential-card"
    }])[0]
    available = build_user_manager_preview([{
        "external_id": "*10", "username": "credential-card", "password": ""
    }])[0]

    assert unavailable["source_fingerprint"] != available["source_fingerprint"]
    assert "password" not in repr(unavailable["safe_snapshot"]).lower()
    assert "password" not in repr(available["safe_snapshot"]).lower()

def test_preview_ignores_null_password_alias_when_another_alias_is_available():
    result = build_user_manager_preview([{
        "external_id": "*11",
        "username": "alias-card",
        "password": None,
        "pass": "available-secret",
    }])[0]

    assert result["credential_mode"] == "separate_credentials"
    assert result["credential_state"] == "plaintext_available"
    assert "available-secret" not in repr(result)
    assert "password" not in result["safe_snapshot"]


def test_preview_marks_conflicting_password_aliases_ambiguous():
    result = build_user_manager_preview([{
        "external_id": "*12",
        "username": "conflicting-card",
        "password": "first-secret",
        "passwd": "second-secret",
    }])[0]

    assert result["credential_mode"] is None
    assert result["credential_state"] == "ambiguous"
    assert any("متعارضة" in issue for issue in result["issues"])
    assert "first-secret" not in repr(result)
    assert "second-secret" not in repr(result)
