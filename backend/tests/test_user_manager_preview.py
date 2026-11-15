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


def test_preview_strips_nested_secrets_and_detects_batch_duplicates():
    records = [
        {"external_id": "*A", "username": "one", "auth": {"password": "x", "method": "pap"}},
        {"external_id": "*A", "username": "two"},
    ]
    result = build_user_manager_preview(records)

    assert result[0]["classification"] == "new"
    assert result[0]["safe_snapshot"]["auth"] == {"method": "pap"}
    assert result[1]["classification"] == "duplicate_in_batch"


def test_preview_rejects_non_object_record():
    try:
        build_user_manager_preview(["not-a-record"])
    except ValueError as exc:
        assert "كائن بيانات" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
