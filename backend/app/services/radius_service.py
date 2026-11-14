import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.core import Card, CardEvent, RadiusSession, Router
from app.services.credentials import (
    CredentialEncryptionNotConfigured,
    decrypt_credential,
)

AUTH_RESERVATION_SECONDS = 120
ALLOWED_PRE_SESSION_STATES = {"generated", "allocated", "printed_free"}
BLOCKED_CARD_STATES = {"suspended", "cancelled", "expired", "exhausted"}


def _utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _snapshot_limit(card: Card, key: str) -> int | None:
    value = (card.plan_snapshot or {}).get(key)
    return int(value) if value is not None else None


def _remaining_limits(card: Card, now: datetime) -> tuple[int | None, int | None]:
    time_limit = _snapshot_limit(card, "session_time_limit_seconds")
    data_limit = _snapshot_limit(card, "data_limit_bytes")
    remaining_time = (
        max(0, time_limit - int(card.used_seconds))
        if time_limit is not None
        else None
    )
    remaining_data = (
        max(0, data_limit - int(card.upload_bytes) - int(card.download_bytes))
        if data_limit is not None
        else None
    )

    if card.expires_at is not None:
        validity_remaining = max(0, int((_utc(card.expires_at) - now).total_seconds()))
        remaining_time = (
            validity_remaining
            if remaining_time is None
            else min(remaining_time, validity_remaining)
        )
    return remaining_time, remaining_data


def _restore_stale_active_status(db: Session, card: Card) -> None:
    previous_session = (
        db.query(RadiusSession)
        .filter(RadiusSession.card_id == card.id)
        .order_by(RadiusSession.id.desc())
        .first()
    )
    previous = (
        previous_session.card_status_before_session
        if previous_session is not None
        else None
    )
    if previous not in ALLOWED_PRE_SESSION_STATES:
        previous = "allocated" if card.assigned_pos_id is not None else (
            "printed_free" if card.is_free else "generated"
        )
    card.status = previous


def authorize_card(
    db: Session,
    *,
    nas_identifier: str,
    username: str,
    password: str,
    framed_ip_address: str | None = None,
    calling_station_id: str | None = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    router = (
        db.query(Router)
        .filter(
            Router.nas_identifier == nas_identifier,
            Router.is_active.is_(True),
        )
        .first()
    )
    if router is None:
        return {"accepted": False, "reason": "NAS غير مسجل أو متوقف", "reply": {}}

    card = (
        db.query(Card)
        .filter(Card.username == username)
        .with_for_update()
        .first()
    )
    if card is None:
        return {"accepted": False, "reason": "الكرت غير موجود", "reply": {}}

    if card.status in BLOCKED_CARD_STATES:
        return {"accepted": False, "reason": "الكرت موقوف أو منتهي", "reply": {}}

    active_session = (
        db.query(RadiusSession.id)
        .filter(
            RadiusSession.card_id == card.id,
            RadiusSession.stopped_at.is_(None),
        )
        .first()
    )
    if active_session is not None:
        return {
            "accepted": False,
            "reason": "الكرت لديه جلسة نشطة ويسمح باتصال واحد فقط",
            "reply": {},
        }

    if card.status == "active":
        _restore_stale_active_status(db, card)

    if card.status not in ALLOWED_PRE_SESSION_STATES:
        return {"accepted": False, "reason": "حالة الكرت لا تسمح بالدخول", "reply": {}}

    if card.radius_auth_reserved_until is not None:
        reserved_until = _utc(card.radius_auth_reserved_until)
        if reserved_until > now:
            return {
                "accepted": False,
                "reason": "يوجد طلب دخول آخر قيد المعالجة لهذا الكرت",
                "reply": {},
            }
        card.radius_auth_reserved_until = None

    try:
        expected_password = decrypt_credential(card.credential_ciphertext)
    except CredentialEncryptionNotConfigured:
        raise
    except ValueError:
        return {
            "accepted": False,
            "reason": "تعذر التحقق من بيانات الكرت بسبب إعداد التشفير",
            "reply": {},
        }

    if not secrets.compare_digest(expected_password, password):
        db.add(
            CardEvent(
                card_id=card.id,
                event_type="radius_auth_rejected",
                details={"nas_identifier": nas_identifier, "reason": "invalid_credentials"},
                actor="radius",
            )
        )
        db.commit()
        return {"accepted": False, "reason": "بيانات الدخول غير صحيحة", "reply": {}}

    if card.first_used_at is None:
        card.first_used_at = now
        validity = _snapshot_limit(card, "validity_period_seconds")
        card.expires_at = (
            now + timedelta(seconds=validity)
            if validity is not None
            else None
        )
        db.add(
            CardEvent(
                card_id=card.id,
                event_type="first_used",
                details={"nas_identifier": nas_identifier},
                actor="radius",
            )
        )

    if card.expires_at is not None and _utc(card.expires_at) <= now:
        card.status = "expired"
        card.radius_auth_reserved_until = None
        db.add(
            CardEvent(
                card_id=card.id,
                event_type="expired",
                details={"source": "radius_authorize"},
                actor="radius",
            )
        )
        db.commit()
        return {"accepted": False, "reason": "انتهت صلاحية الكرت", "reply": {}}

    remaining_time, remaining_data = _remaining_limits(card, now)
    if remaining_time is not None and remaining_time <= 0:
        card.status = "exhausted"
        card.radius_auth_reserved_until = None
        db.commit()
        return {"accepted": False, "reason": "انتهى رصيد وقت الاستخدام", "reply": {}}
    if remaining_data is not None and remaining_data <= 0:
        card.status = "exhausted"
        card.radius_auth_reserved_until = None
        db.commit()
        return {"accepted": False, "reason": "انتهى رصيد البيانات", "reply": {}}

    # Reserve the card atomically before Access-Accept. Accounting-Start consumes this lease.
    card.radius_auth_reserved_until = now + timedelta(seconds=AUTH_RESERVATION_SECONDS)
    router.last_seen_at = now

    reply: dict[str, str | int] = {
        "Port-Limit": 1,
        "Acct-Interim-Interval": 60,
    }
    speed_profile = (card.plan_snapshot or {}).get("speed_profile")
    if speed_profile:
        reply["Mikrotik-Rate-Limit"] = str(speed_profile)
    if remaining_time is not None:
        reply["Session-Timeout"] = remaining_time
    if remaining_data is not None:
        reply["Mikrotik-Total-Limit"] = remaining_data

    db.add(
        CardEvent(
            card_id=card.id,
            event_type="radius_auth_accepted",
            details={
                "nas_identifier": nas_identifier,
                "framed_ip_address": framed_ip_address,
                "calling_station_id": calling_station_id,
                "reservation_seconds": AUTH_RESERVATION_SECONDS,
            },
            actor="radius",
        )
    )
    db.commit()
    return {"accepted": True, "reason": "تم قبول المصادقة", "reply": reply}


def _packet_fingerprint(payload: dict[str, Any]) -> str:
    normalized = json.dumps(
        payload,
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _octets(payload: dict[str, Any], octets_key: str, gigawords_key: str) -> int:
    return int(payload.get(octets_key, 0)) + int(payload.get(gigawords_key, 0)) * (2**32)


def process_accounting(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    router = (
        db.query(Router)
        .filter(Router.nas_identifier == payload["nas_identifier"])
        .first()
    )
    if router is None:
        return {"processed": False, "reason": "NAS غير مسجل"}

    card = (
        db.query(Card)
        .filter(Card.username == payload["username"])
        .with_for_update()
        .first()
    )
    if card is None:
        return {"processed": False, "reason": "الكرت غير موجود"}

    event_time = _utc(payload.get("event_timestamp"))
    fingerprint = _packet_fingerprint(payload)
    session = (
        db.query(RadiusSession)
        .filter(
            RadiusSession.router_id == router.id,
            RadiusSession.acct_session_id == payload["acct_session_id"],
        )
        .with_for_update()
        .first()
    )

    if session is not None and session.card_id != card.id:
        return {"processed": False, "reason": "معرّف الجلسة مرتبط بكرت آخر"}

    status_type = payload["status_type"]
    if not router.is_active:
        if status_type == "Start" or session is None:
            return {"processed": False, "reason": "الراوتر متوقف ولا يسمح ببدء جلسات جديدة"}
    if status_type == "Start":
        if session is not None:
            if session.stopped_at is not None:
                return {"processed": False, "reason": "معرّف الجلسة سبق إغلاقه"}
            return {
                "processed": True,
                "duplicate": True,
                "disconnect_required": False,
                "reason": "Accounting-Start مكرر",
            }

        if card.status in BLOCKED_CARD_STATES:
            return {"processed": False, "reason": "حالة الكرت لا تسمح ببدء الجلسة"}

        other_active_session = (
            db.query(RadiusSession.id)
            .filter(
                RadiusSession.card_id == card.id,
                RadiusSession.stopped_at.is_(None),
            )
            .first()
        )
        if other_active_session is not None:
            return {"processed": False, "reason": "للكرت جلسة نشطة أخرى"}

        if card.status == "active":
            _restore_stale_active_status(db, card)
        if card.status not in ALLOWED_PRE_SESSION_STATES:
            return {"processed": False, "reason": "حالة الكرت لا تسمح ببدء الجلسة"}
        if card.expires_at is not None and _utc(card.expires_at) <= event_time:
            card.status = "expired"
            card.radius_auth_reserved_until = None
            db.commit()
            return {"processed": False, "reason": "انتهت صلاحية الكرت قبل بدء الجلسة"}

        reservation = card.radius_auth_reserved_until
        if reservation is None or _utc(reservation) <= datetime.now(timezone.utc):
            return {
                "processed": False,
                "reason": "لا يوجد حجز مصادقة صالح لهذه الجلسة",
            }

        if card.first_used_at is None:
            card.first_used_at = event_time
            validity = _snapshot_limit(card, "validity_period_seconds")
            card.expires_at = (
                event_time + timedelta(seconds=validity)
                if validity is not None
                else None
            )
            db.add(
                CardEvent(
                    card_id=card.id,
                    event_type="first_used",
                    details={"nas_identifier": router.nas_identifier},
                    actor="radius",
                )
            )

        input_total = _octets(payload, "input_octets", "input_gigawords")
        output_total = _octets(payload, "output_octets", "output_gigawords")
        session_time = int(payload.get("session_time_seconds", 0))
        previous_status = card.status
        session = RadiusSession(
            card_id=card.id,
            router_id=router.id,
            acct_session_id=payload["acct_session_id"],
            framed_ip_address=payload.get("framed_ip_address"),
            calling_station_id=payload.get("calling_station_id"),
            started_at=event_time,
            last_update_at=event_time,
            stopped_at=None,
            input_octets=input_total,
            output_octets=output_total,
            session_time_seconds=session_time,
            last_packet_fingerprint=fingerprint,
            card_status_before_session=previous_status,
        )
        db.add(session)
        card.upload_bytes += input_total
        card.download_bytes += output_total
        card.used_seconds += session_time
        remaining_time, remaining_data = _remaining_limits(card, event_time)
        disconnect_required = (
            (remaining_time is not None and remaining_time <= 0)
            or (remaining_data is not None and remaining_data <= 0)
        )
        card.status = "exhausted" if disconnect_required else "active"
        card.radius_auth_reserved_until = None
        router.last_seen_at = max(_utc(router.last_seen_at), event_time)
        db.add(
            CardEvent(
                card_id=card.id,
                event_type="radius_session_started",
                details={
                    "acct_session_id": payload["acct_session_id"],
                    "nas_identifier": router.nas_identifier,
                },
                actor="radius",
            )
        )
        db.commit()
        return {
            "processed": True,
            "duplicate": False,
            "disconnect_required": disconnect_required,
            "reason": "بدأت الجلسة؛ يجب الفصل فوراً لتجاوز أحد الحدود" if disconnect_required else "بدأت الجلسة",
        }

    if session is None:
        return {
            "processed": False,
            "reason": "لم يتم العثور على Accounting-Start لهذه الجلسة",
        }
    if session.stopped_at is not None:
        return {
            "processed": True,
            "duplicate": True,
            "disconnect_required": False,
            "reason": "الجلسة مغلقة مسبقاً",
        }
    if session.last_packet_fingerprint == fingerprint:
        return {
            "processed": True,
            "duplicate": True,
            "disconnect_required": False,
            "reason": "حزمة مكررة تم تجاهلها",
        }

    new_input = max(
        int(session.input_octets),
        _octets(payload, "input_octets", "input_gigawords"),
    )
    new_output = max(
        int(session.output_octets),
        _octets(payload, "output_octets", "output_gigawords"),
    )
    new_time = max(
        int(session.session_time_seconds),
        int(payload.get("session_time_seconds", 0)),
    )

    card.upload_bytes += new_input - int(session.input_octets)
    card.download_bytes += new_output - int(session.output_octets)
    card.used_seconds += new_time - int(session.session_time_seconds)

    session.input_octets = new_input
    session.output_octets = new_output
    session.session_time_seconds = new_time
    if session.last_update_at is None or event_time >= _utc(session.last_update_at):
        session.last_update_at = event_time
    session.framed_ip_address = payload.get("framed_ip_address") or session.framed_ip_address
    session.calling_station_id = payload.get("calling_station_id") or session.calling_station_id
    session.last_packet_fingerprint = fingerprint
    router.last_seen_at = max(_utc(router.last_seen_at), event_time)

    disconnect_required = card.status in {"suspended", "exhausted"} or not router.is_active
    reason = "الكرت أو الراوتر متوقف ويجب فصل الجلسة" if disconnect_required else "تم تحديث المحاسبة"
    remaining_time, remaining_data = _remaining_limits(card, event_time)
    if remaining_time is not None and remaining_time <= 0:
        card.status = "exhausted"
        disconnect_required = True
        reason = "انتهى رصيد وقت الاستخدام ويجب فصل الجلسة"
    elif remaining_data is not None and remaining_data <= 0:
        card.status = "exhausted"
        disconnect_required = True
        reason = "انتهى رصيد البيانات ويجب فصل الجلسة"

    if status_type == "Stop":
        stop_time = max(event_time, _utc(session.last_update_at))
        session.stopped_at = stop_time
        card.radius_auth_reserved_until = None
        if card.status == "active":
            previous_status = session.card_status_before_session
            if previous_status not in ALLOWED_PRE_SESSION_STATES:
                previous_status = "allocated" if card.assigned_pos_id is not None else (
                    "printed_free" if card.is_free else "generated"
                )
            card.status = previous_status
        if card.status != "exhausted" and card.expires_at is not None and _utc(card.expires_at) <= stop_time:
            card.status = "expired"
        db.add(
            CardEvent(
                card_id=card.id,
                event_type="radius_session_stopped",
                details={
                    "acct_session_id": payload["acct_session_id"],
                    "session_time_seconds": new_time,
                    "input_octets": new_input,
                    "output_octets": new_output,
                },
                actor="radius",
            )
        )
        disconnect_required = False
        reason = "انتهت الجلسة"

    db.commit()
    return {
        "processed": True,
        "duplicate": False,
        "disconnect_required": disconnect_required,
        "reason": reason,
    }
