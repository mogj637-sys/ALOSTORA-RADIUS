"""Deterministic, side-effect-free classification for User Manager import previews."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable


SENSITIVE_KEYS = {
    "password", "passwd", "secret", "credential", "credential_ciphertext",
    "password-hash", "password_hash", "verifier", "hash",
}


def _safe_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {
            str(key): _safe_value(item)
            for key, item in value.items()
            if str(key).strip().lower() not in SENSITIVE_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [_safe_value(item) for item in value]
    return str(value)


def _fingerprint(snapshot: dict[str, Any]) -> str:
    encoded = json.dumps(
        snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_user_manager_preview(
    records: Iterable[dict[str, Any]],
    *,
    existing_cards_by_username: dict[str, Any] | None = None,
    source_links_by_external_id: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Classify a bounded source batch without mutating input or persistence."""
    cards = existing_cards_by_username or {}
    links = source_links_by_external_id or {}
    output: list[dict[str, Any]] = []
    seen_external_ids: set[str] = set()

    for record in records:
        if not isinstance(record, dict):
            raise ValueError("كل سجل مصدر يجب أن يكون كائن بيانات")

        username = str(record.get("username") or "").strip()
        external_id_value = record.get("external_id", record.get(".id"))
        external_id = (
            str(external_id_value).strip()
            if external_id_value is not None else ""
        )
        profile = record.get("actual_profile") or record.get("actual-profile")
        safe_snapshot = _safe_value(record)
        issues: list[str] = []

        if not username:
            classification = "invalid"
            issues.append("اسم المستخدم غير موجود")
        elif not external_id:
            classification = "invalid"
            issues.append("معرف User Manager الأصلي غير متاح؛ لا يمكن ضمان منع التكرار")
        elif external_id in seen_external_ids:
            classification = "duplicate_in_batch"
            issues.append("تكرر معرف المصدر داخل الدفعة نفسها")
        elif external_id in links:
            classification = "already_linked"
        elif username in cards:
            classification = "username_conflict"
            issues.append("اسم المستخدم موجود مسبقاً في ALOSTORA دون رابط مصدر مطابق")
        else:
            classification = "new"

        if external_id:
            seen_external_ids.add(external_id)

        matched_card_id = links.get(external_id) if external_id else None
        if matched_card_id is None and classification == "username_conflict":
            matched_card_id = cards.get(username)

        output.append({
            "external_user_id": external_id or None,
            "username": username or None,
            "source_profile_id": str(profile) if profile is not None else None,
            "classification": classification,
            "matched_card_id": str(matched_card_id) if matched_card_id is not None else None,
            "safe_snapshot": safe_snapshot,
            "issues": issues,
            "source_fingerprint": _fingerprint(safe_snapshot),
        })

    return output
