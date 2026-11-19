"""Deterministic, side-effect-free classification for User Manager import previews."""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Iterable


def _normalized_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).strip().lower())


# Match common RouterOS/API spellings as well as application credential fields.
SENSITIVE_KEYS = {
    "password", "passwd", "pass", "userpassword", "cleartextpassword",
    "passwordplaintext", "plaintextpassword", "secret", "apisecret",
    "apipassword", "routerpassword", "routerospassword", "radiussecret",
    "sharedsecret", "clientsecret", "passphrase", "token", "accesstoken",
    "authtoken", "credential", "credentialciphertext", "passwordhash",
    "hashpassword", "verifier", "hash",
}
VERIFIER_KEYS = {"passwordhash", "hashpassword", "verifier", "hash"}
PASSWORD_KEYS = (
    "password",
    "passwd",
    "pass",
    "userpassword",
    "cleartextpassword",
    "passwordplaintext",
    "plaintextpassword",
)


def _safe_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {
            str(key): _safe_value(item)
            for key, item in value.items()
            if _normalized_key(key) not in SENSITIVE_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [_safe_value(item) for item in value]
    return str(value)


def _credential_metadata(record: dict[str, Any], username: str) -> dict[str, str | None]:
    """Infer only credential shape; never return or persist a credential value."""
    normalized = {_normalized_key(key): value for key, value in record.items()}

    if any(key in normalized and normalized[key] not in (None, "") for key in VERIFIER_KEYS):
        return {"credential_mode": None, "credential_state": "verifier_unverified"}

    password_values = [
        str(normalized[key])
        for key in PASSWORD_KEYS
        if key in normalized and normalized[key] is not None
    ]
    if not password_values:
        return {"credential_mode": None, "credential_state": "unavailable"}

    # Router/API adapters can expose the same credential under multiple aliases.
    # Conflicting values are ambiguous; never choose one by unordered set order.
    if len(set(password_values)) != 1:
        return {"credential_mode": None, "credential_state": "ambiguous"}

    password = password_values[0]
    if password == "":
        return {"credential_mode": "username_only", "credential_state": "plaintext_available"}
    if password == username:
        return {"credential_mode": "same_credentials", "credential_state": "plaintext_available"}
    return {"credential_mode": "separate_credentials", "credential_state": "plaintext_available"}


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
        credential = _credential_metadata(record, username)
        issues: list[str] = []

        if credential["credential_state"] == "unavailable":
            issues.append("بيانات الاعتماد غير متاحة في سجل المصدر")
        elif credential["credential_state"] == "ambiguous":
            issues.append("حقول كلمة المرور في سجل المصدر متعارضة؛ يلزم التحقق اليدوي")
        elif credential["credential_state"] == "verifier_unverified":
            issues.append("صيغة hash/verifier غير مثبتة التوافق مع مصادقة RADIUS")

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
            "credential_mode": credential["credential_mode"],
            "credential_state": credential["credential_state"],
            "safe_snapshot": safe_snapshot,
            "issues": issues,
            "source_fingerprint": _fingerprint({
                "safe_snapshot": safe_snapshot,
                "credential_mode": credential["credential_mode"],
                "credential_state": credential["credential_state"],
            }),
        })

    return output
