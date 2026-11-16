import secrets
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.auth import AdminUser
from app.models.core import Card, CardBatch, CardEvent, CardTemplate, Plan, PointOfSale, RadiusSession, Router
from app.services.radius_disconnect import send_disconnect_for_session
from app.services.audit import record_audit
from app.schemas.cards import (
    CardBatchCreate,
    CardBatchResponse,
    CardBatchListItem,
    CardCreatedSecret,
    CardCreateResponse,
    CardListItem,
    CardSingleCreate,
    CardStatusUpdate,
    CardPrintSelectionResolveRequest,
    CardPrintSelectionResolveResponse,
    CardPrintSelectionItem,
)
from app.services.card_generator import generate_password, generate_username
from app.services.credentials import CredentialEncryptionNotConfigured, encrypt_credential
from app.services.pos_credit import ensure_pos_card_creation_allowed
from app.services.permissions import card_visibility, is_owner

router = APIRouter(prefix="/api/v1/cards", tags=["cards"])


def _plan_snapshot(plan: Plan) -> dict:
    return {
        "id": plan.id,
        "code": plan.code,
        "name": plan.name,
        "price": str(plan.price),
        "data_limit_bytes": plan.data_limit_bytes,
        "session_time_limit_seconds": plan.session_time_limit_seconds,
        "validity_period_seconds": plan.validity_period_seconds,
        "speed_profile": plan.speed_profile,
        "settings": plan.settings or {},
    }


def _new_serial() -> str:
    return "AL" + secrets.token_hex(5).upper()


def _credential_for(card_type: str, username: str, supplied_password: str | None) -> str:
    if card_type == "username_only":
        if supplied_password:
            raise HTTPException(status_code=422, detail="هذا النوع لا يستخدم كلمة مرور")
        return ""
    if card_type == "same_credentials":
        if supplied_password and supplied_password != username:
            raise HTTPException(status_code=422, detail="في هذا النوع يجب أن تطابق كلمة المرور اسم المستخدم")
        return username
    if card_type == "separate_credentials":
        if not supplied_password:
            raise HTTPException(status_code=422, detail="أدخل كلمة المرور لهذا النوع من الكروت")
        return supplied_password
    raise HTTPException(status_code=422, detail="نوع الكرت غير معروف")


def _ensure_encryption_ready() -> None:
    try:
        encrypt_credential("configuration-check")
    except CredentialEncryptionNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc))


def _build_card(plan: Plan, username: str, password: str, card_type: str, is_free: bool = False, batch_id=None) -> Card:
    return Card(
        serial_number=_new_serial(),
        username=username,
        credential_ciphertext=encrypt_credential(password),
        credential_scheme="fernet_v1",
        card_type=card_type,
        status="generated",
        is_free=is_free,
        plan_id=plan.id,
        batch_id=batch_id,
        plan_snapshot=_plan_snapshot(plan),
        price_snapshot=0 if is_free else plan.price,
    )


@router.get("/batches", response_model=list[CardBatchListItem])
def list_card_batches(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_permission("cards.view")),
):
    visibility = card_visibility(user)
    assigned_pos_ids = [point.id for point in user.point_of_sales]
    if visibility == "search_any":
        return []
    rows_query = (
        db.query(CardBatch, Plan, PointOfSale)
        .join(Plan, Plan.id == CardBatch.plan_id)
        .outerjoin(PointOfSale, PointOfSale.id == CardBatch.point_of_sale_id)
        .order_by(CardBatch.created_at.desc())
    )
    if visibility == "assigned":
        rows_query = rows_query.filter(CardBatch.point_of_sale_id.in_(assigned_pos_ids)) if assigned_pos_ids else rows_query.filter(CardBatch.id.is_(None))
    rows = rows_query.limit(limit).all()
    results = []
    for batch, plan, point in rows:
        printed = (
            db.query(func.count(func.distinct(Card.id)))
            .join(CardEvent, CardEvent.card_id == Card.id)
            .filter(
                Card.batch_id == batch.id,
                CardEvent.event_type.in_(["printed_to_pos", "printed_free"]),
            )
            .scalar() or 0
        )
        results.append(CardBatchListItem(
            batch_id=batch.id,
            batch_number=batch.batch_number,
            plan_id=batch.plan_id,
            plan_name=plan.name,
            template_code=batch.template_code,
            point_of_sale_id=batch.point_of_sale_id,
            point_of_sale_name=point.name if point else None,
            quantity=batch.quantity,
            card_type=batch.card_type,
            generation_mode=batch.generation_mode,
            username_length=batch.username_length,
            password_length=batch.password_length,
            prefix=batch.prefix,
            created_at=batch.created_at,
            printed_count=printed,
            is_online_sale=batch.is_online_sale,
            note=batch.note,
        ))
    return results


@router.get("/overview")
def get_radius_overview(db: Session = Depends(get_db), user: AdminUser = Depends(require_permission("cards.view"))):
    """Return database-backed totals for the admin dashboard."""
    visibility = card_visibility(user)
    assigned_pos_ids = [point.id for point in user.point_of_sales]
    card_query = db.query(Card)
    session_query = db.query(RadiusSession)
    if visibility == "assigned":
        scoped_ids = (
            db.query(Card.id).filter(
                or_(
                    Card.assigned_pos_id.in_(assigned_pos_ids),
                    Card.batch_id.in_(db.query(CardBatch.id).filter(CardBatch.point_of_sale_id.in_(assigned_pos_ids))),
                )
            ) if assigned_pos_ids else db.query(Card.id).filter(Card.id.is_(None))
        )
        card_query = card_query.filter(Card.id.in_(scoped_ids))
        session_query = session_query.filter(RadiusSession.card_id.in_(scoped_ids))
    elif visibility == "search_any":
        card_query = card_query.filter(Card.id.is_(None))
        session_query = session_query.filter(RadiusSession.id.is_(None))
    card_counts = dict(card_query.with_entities(Card.status, func.count(Card.id)).group_by(Card.status).all())
    active_sessions = (
        session_query.with_entities(func.count(RadiusSession.id))
        .filter(RadiusSession.stopped_at.is_(None))
        .scalar() or 0
    )
    active_users = (
        session_query.with_entities(func.count(func.distinct(RadiusSession.card_id)))
        .filter(RadiusSession.stopped_at.is_(None))
        .scalar() or 0
    )
    total_sessions = session_query.with_entities(func.count(RadiusSession.id)).scalar() or 0
    routers_total = db.query(func.count(Router.id)).scalar() or 0
    routers_enabled = db.query(func.count(Router.id)).filter(Router.is_active.is_(True)).scalar() or 0
    plans_total = db.query(func.count(Plan.id)).scalar() or 0
    plans_enabled = db.query(func.count(Plan.id)).filter(Plan.is_active.is_(True)).scalar() or 0
    return {
        "database_status": "connected",
        "cards_total": int(sum(card_counts.values())),
        "cards_by_status": {str(key): int(value) for key, value in card_counts.items()},
        "active_sessions": int(active_sessions),
        "active_users": int(active_users),
        "sessions_total": int(total_sessions),
        "routers_total": int(routers_total),
        "routers_enabled": int(routers_enabled),
        "plans_total": int(plans_total),
        "plans_enabled": int(plans_enabled),
    }


@router.get("/sessions", dependencies=[Depends(require_permission("sessions.view"))])
def list_radius_sessions(
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_permission("sessions.view")),
):
    """Return live RADIUS sessions and aggregate counters for the admin dashboard."""
    visibility = card_visibility(user)
    assigned_pos_ids = [point.id for point in user.point_of_sales]
    if visibility == "search_any":
        raise HTTPException(status_code=403, detail="هذا الحساب مخوّل بالبحث عن جلسات كرت محدد فقط")
    session_query = db.query(RadiusSession)
    if visibility == "assigned":
        scoped_ids = db.query(Card.id).filter(Card.assigned_pos_id.in_(assigned_pos_ids)) if assigned_pos_ids else db.query(Card.id).filter(Card.id.is_(None))
        session_query = session_query.filter(RadiusSession.card_id.in_(scoped_ids))
    active_count = (
        session_query.with_entities(func.count(RadiusSession.id))
        .filter(RadiusSession.stopped_at.is_(None))
        .scalar() or 0
    )
    active_users_count = (
        session_query.with_entities(func.count(func.distinct(RadiusSession.card_id)))
        .filter(RadiusSession.stopped_at.is_(None))
        .scalar() or 0
    )
    total_count = session_query.with_entities(func.count(RadiusSession.id)).scalar() or 0
    rows_query = db.query(RadiusSession, Card, Router).join(Card, Card.id == RadiusSession.card_id).join(Router, Router.id == RadiusSession.router_id)
    if visibility == "assigned":
        rows_query = rows_query.filter(Card.assigned_pos_id.in_(assigned_pos_ids)) if assigned_pos_ids else rows_query.filter(RadiusSession.id.is_(None))
    rows = (
        rows_query
        .filter(RadiusSession.stopped_at.is_(None))
        .order_by(RadiusSession.started_at.desc())
        .limit(limit)
        .all()
    )
    return {
        "active_count": int(active_count),
        "active_users_count": int(active_users_count),
        "total_count": int(total_count),
        "items": [
            {
                "id": session.id,
                "username": card.username,
                "serial_number": card.serial_number,
                "card_status": card.status,
                "router_name": router.name,
                "nas_identifier": router.nas_identifier,
                "acct_session_id": session.acct_session_id,
                "framed_ip_address": session.framed_ip_address,
                "calling_station_id": session.calling_station_id,
                "started_at": session.started_at,
                "last_update_at": session.last_update_at,
                "session_time_seconds": session.session_time_seconds,
                "upload_bytes": session.input_octets,
                "download_bytes": session.output_octets,
            }
            for session, card, router in rows
        ],
    }


@router.post("/sessions/{session_id}/disconnect", dependencies=[Depends(require_permission("sessions.disconnect"))])
def disconnect_radius_session(session_id: int, db: Session = Depends(get_db), user: AdminUser = Depends(require_permission("sessions.disconnect"))):
    session = db.query(RadiusSession).filter(RadiusSession.id == session_id).first()
    if session is None:
        raise HTTPException(status_code=404, detail="جلسة المستخدم غير موجودة")
    if session.stopped_at is not None:
        raise HTTPException(status_code=409, detail="الجلسة منتهية بالفعل")
    visibility = card_visibility(user)
    if visibility == "assigned":
        assigned_pos_ids = {point.id for point in user.point_of_sales}
        session_card = db.get(Card, session.card_id)
        if session_card is None or session_card.assigned_pos_id not in assigned_pos_ids:
            raise HTTPException(status_code=403, detail="لا تملك صلاحية فصل جلسة هذا الكرت")
    result = send_disconnect_for_session(db, session)
    if result is None:
        raise HTTPException(status_code=503, detail="خدمة فصل الجلسات RADIUS CoA غير مفعلة")
    if not result:
        raise HTTPException(status_code=502, detail="لم يؤكد الراوتر فصل الجلسة")
    session_card = db.get(Card, session.card_id)
    session_username = session_card.username if session_card else str(session.card_id)
    record_audit(db, user, "session.disconnect_requested", "radius_session", f"طلب فصل جلسة المستخدم {session_username}", entity_id=session.id, details={"router_id": session.router_id, "acct_session_id": session.acct_session_id})
    db.commit()
    return {"session_id": session.id, "disconnect_acknowledged": True, "message": "أكد الراوتر استلام طلب فصل الجلسة"}


@router.get("", response_model=list[CardListItem])
def list_cards(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    status_filter: str | None = Query(default=None, alias="status"),
    search: str | None = Query(default=None, min_length=1, max_length=120),
    plan_id: int | None = Query(default=None, gt=0),
    batch_id: UUID | None = Query(default=None),
    is_free: bool | None = None,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_permission("cards.view")),
):
    visibility = card_visibility(user)
    assigned_pos_ids = [point.id for point in user.point_of_sales]
    query = db.query(Card)
    if visibility == "assigned":
        query = query.filter(
            or_(
                Card.assigned_pos_id.in_(assigned_pos_ids),
                Card.batch_id.in_(db.query(CardBatch.id).filter(CardBatch.point_of_sale_id.in_(assigned_pos_ids))),
            )
        ) if assigned_pos_ids else query.filter(Card.id.is_(None))
    if visibility == "search_any":
        if not search or search.strip() != search:
            raise HTTPException(status_code=403, detail="يجب البحث باسم المستخدم أو الرقم التسلسلي كاملاً")
        exact_term = search.strip()
        query = query.filter(
            or_(
                func.lower(Card.username) == exact_term.lower(),
                func.lower(Card.serial_number) == exact_term.lower(),
            )
        )
    elif search:
        term = f"%{search.strip()}%"
        query = query.filter(or_(Card.username.ilike(term), Card.serial_number.ilike(term)))
    now = datetime.now(timezone.utc)
    if status_filter == "expired":
        query = query.filter(
            or_(
                Card.status == "expired",
                and_(
                    Card.expires_at.is_not(None),
                    Card.expires_at <= now,
                    Card.status.notin_(["suspended", "cancelled", "exhausted"]),
                ),
            )
        )
    elif status_filter:
        query = query.filter(Card.status == status_filter)
        if status_filter not in {"suspended", "cancelled", "exhausted"}:
            query = query.filter(or_(Card.expires_at.is_(None), Card.expires_at > now))
    if plan_id is not None:
        query = query.filter(Card.plan_id == plan_id)
    if batch_id is not None:
        query = query.filter(Card.batch_id == batch_id)
    if is_free is not None:
        query = query.filter(Card.is_free.is_(is_free))
    cards = (
        query.order_by(Card.created_at.desc())
        .offset(offset if visibility != "search_any" else 0)
        .limit(limit if visibility != "search_any" else 1)
        .all()
    )
    if not cards:
        return cards
    session_counts = dict(
        db.query(RadiusSession.card_id, func.count(RadiusSession.id))
        .filter(
            RadiusSession.card_id.in_([card.id for card in cards]),
            RadiusSession.stopped_at.is_(None),
        )
        .group_by(RadiusSession.card_id)
        .all()
    )
    for card in cards:
        if (
            card.expires_at is not None
            and card.expires_at <= now
            and card.status not in {"suspended", "cancelled", "exhausted"}
        ):
            card.status = "expired"
        card.active_sessions_count = int(session_counts.get(card.id, 0))
    return cards


@router.post(
    "/print-selection/resolve",
    response_model=CardPrintSelectionResolveResponse,
    dependencies=[Depends(require_permission("printing.create")), Depends(require_permission("cards.view")), Depends(require_permission("pos.view"))],
)
def resolve_print_selection(
    payload: CardPrintSelectionResolveRequest,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_permission("printing.create")),
):
    point = db.get(PointOfSale, payload.point_of_sale_id)
    if point is None:
        raise HTTPException(status_code=404, detail="نقطة البيع غير موجودة")
    if not point.is_active or not point.allow_printing:
        raise HTTPException(status_code=409, detail="الطباعة متوقفة لهذه النقطة")
    if not is_owner(user) and point.id not in {item.id for item in user.point_of_sales}:
        raise HTTPException(status_code=403, detail="لا تملك صلاحية الطباعة في نقطة البيع المحددة")

    identifiers = list(dict.fromkeys(value.strip() for value in payload.identifiers if value.strip()))
    normalized = [value.lower() for value in identifiers]
    query = db.query(Card).filter(
        Card.status == "generated",
        Card.assigned_pos_id.is_(None),
        or_(
            func.lower(Card.username).in_(normalized),
            func.lower(Card.serial_number).in_(normalized),
        ),
    )

    batch_ids_for_point = db.query(CardBatch.id).filter(CardBatch.point_of_sale_id == point.id)
    if card_visibility(user) == "assigned":
        query = query.filter(Card.batch_id.in_(batch_ids_for_point))
    else:
        allowed_batch_ids = db.query(CardBatch.id).filter(
            or_(
                CardBatch.point_of_sale_id == point.id,
                CardBatch.point_of_sale_id.is_(None),
            )
        )
        query = query.filter(
            or_(
                Card.batch_id.is_(None),
                Card.batch_id.in_(allowed_batch_ids),
            )
        )

    matches = query.all()
    by_identifier: dict[str, Card] = {}
    for card in matches:
        by_identifier[card.username.lower()] = card
        by_identifier[card.serial_number.lower()] = card

    items = []
    unmatched = []
    seen_card_ids = set()
    for identifier in identifiers:
        card = by_identifier.get(identifier.lower())
        if card is None:
            unmatched.append(identifier)
        elif card.id not in seen_card_ids:
            items.append(CardPrintSelectionItem(
                id=card.id,
                username=card.username,
                serial_number=card.serial_number,
                plan_id=card.plan_id,
                is_free=card.is_free,
            ))
            seen_card_ids.add(card.id)

    return CardPrintSelectionResolveResponse(
        total_requested=len(identifiers),
        matched_count=len(items),
        items=items,
        unmatched=unmatched,
    )


@router.get("/{card_id}/sessions", dependencies=[Depends(require_permission("sessions.view"))])
def list_card_session_history(
    card_id: str,
    search: str = Query(..., min_length=1, max_length=120),
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_permission("sessions.view")),
):
    """Return the complete RADIUS session history for one explicitly searched card."""
    try:
        card_uuid = UUID(card_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="معرّف الكرت غير صالح")

    card = db.query(Card).filter(Card.id == card_uuid).first()
    if card is None:
        raise HTTPException(status_code=404, detail="الكرت غير موجود")

    visibility = card_visibility(user)
    exact_term = search.strip().lower()
    if not exact_term:
        raise HTTPException(status_code=422, detail="أدخل اسم المستخدم أو الرقم التسلسلي كاملاً")
    if visibility == "search_any" and exact_term not in {card.username.lower(), card.serial_number.lower()}:
        raise HTTPException(status_code=404, detail="لم يتم العثور على الكرت بهذا البحث")
    if visibility == "assigned":
        assigned_pos_ids = [point.id for point in user.point_of_sales]
        in_scope = card.assigned_pos_id in assigned_pos_ids or (
            card.batch_id is not None
            and db.query(CardBatch.id).filter(
                CardBatch.id == card.batch_id,
                CardBatch.point_of_sale_id.in_(assigned_pos_ids),
            ).first() is not None
        )
        if not in_scope:
            raise HTTPException(status_code=403, detail="الكرت خارج نطاق نقاط البيع المسموح بها")

    rows = (
        db.query(RadiusSession, Router)
        .join(Router, Router.id == RadiusSession.router_id)
        .filter(RadiusSession.card_id == card.id)
        .order_by(RadiusSession.started_at.desc(), RadiusSession.id.desc())
        .all()
    )
    active_count = sum(1 for session, _ in rows if session.stopped_at is None)
    return {
        "card_id": str(card.id),
        "username": card.username,
        "serial_number": card.serial_number,
        "total_sessions": len(rows),
        "active_sessions": active_count,
        "items": [
            {
                "id": session.id,
                "router_name": router_item.name,
                "nas_identifier": router_item.nas_identifier,
                "acct_session_id": session.acct_session_id,
                "framed_ip_address": session.framed_ip_address,
                "calling_station_id": session.calling_station_id,
                "started_at": session.started_at,
                "last_update_at": session.last_update_at,
                "stopped_at": session.stopped_at,
                "session_time_seconds": session.session_time_seconds,
                "upload_bytes": session.input_octets,
                "download_bytes": session.output_octets,
            }
            for session, router_item in rows
        ],
    }


@router.patch("/{card_id}/status", response_model=CardListItem, dependencies=[Depends(require_permission("cards.update"))])
def update_card_status(
    card_id: str,
    payload: CardStatusUpdate,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_permission("cards.update")),
):
    from uuid import UUID

    try:
        card_uuid = UUID(card_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="معرّف الكرت غير صالح")

    card = db.query(Card).filter(Card.id == card_uuid).with_for_update().first()
    if card is None:
        raise HTTPException(status_code=404, detail="الكرت غير موجود")
    visibility = card_visibility(user)
    if visibility == "assigned":
        allowed_pos_ids = [point.id for point in user.point_of_sales]
        in_scope = card.assigned_pos_id in allowed_pos_ids or (
            card.batch_id is not None
            and db.query(CardBatch.id).filter(
                CardBatch.id == card.batch_id,
                CardBatch.point_of_sale_id.in_(allowed_pos_ids),
            ).first() is not None
        )
        if not in_scope:
            raise HTTPException(status_code=403, detail="الكرت خارج نطاق نقاط البيع المسموح بها")

    previous_status = card.status
    if payload.action == "suspend":
        if previous_status not in {"generated", "allocated", "active", "printed_free"}:
            raise HTTPException(status_code=409, detail="لا يمكن إيقاف الكرت في حالته الحالية")
        card.status = "suspended"
        event_type = "suspended"
        details = {"previous_status": previous_status}
    elif payload.action == "reactivate":
        if previous_status != "suspended":
            raise HTTPException(status_code=409, detail="الكرت ليس موقوفاً")
        prior_event = (
            db.query(CardEvent)
            .filter(CardEvent.card_id == card.id, CardEvent.event_type == "suspended")
            .order_by(CardEvent.created_at.desc(), CardEvent.id.desc())
            .first()
        )
        restored_status = (prior_event.details or {}).get("previous_status") if prior_event else None
        if restored_status not in {"generated", "allocated", "active", "printed_free"}:
            restored_status = "active" if card.first_used_at else ("allocated" if card.assigned_pos_id else "generated")
        card.status = restored_status
        event_type = "reactivated"
        details = {"restored_status": restored_status}
    else:  # cancel
        if previous_status not in {"generated", "printed_free"} or card.first_used_at is not None or card.assigned_pos_id is not None:
            raise HTTPException(status_code=409, detail="لا يمكن إلغاء كرت بدأ استخدامه أو تم تخصيصه لنقطة بيع")
        card.status = "cancelled"
        event_type = "cancelled"
        details = {"previous_status": previous_status}

    db.add(CardEvent(
        card_id=card.id,
        event_type=event_type,
        details=details,
        actor=user.username,
    ))
    record_audit(db, user, f"card.{event_type}", "card", f"{event_type} للكرت {card.username}", entity_id=card.id, details={"serial_number": card.serial_number, **details})
    db.commit()
    if payload.action == "suspend":
        active_sessions = (
            db.query(RadiusSession)
            .filter(
                RadiusSession.card_id == card.id,
                RadiusSession.stopped_at.is_(None),
            )
            .all()
        )
        for active_session in active_sessions:
            disconnect_sent = send_disconnect_for_session(db, active_session)
            if disconnect_sent is not None:
                db.add(CardEvent(
                    card_id=card.id,
                    event_type="radius_disconnect_sent" if disconnect_sent else "radius_disconnect_failed",
                    details={"acct_session_id": active_session.acct_session_id, "reason": "admin_suspend"},
                    actor=user.username,
                ))
        if active_sessions:
            db.commit()
    db.refresh(card)
    return card


@router.post("/single", response_model=CardCreateResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission("cards.create")), Depends(require_permission("cards.credentials"))])
def create_single_card(payload: CardSingleCreate, db: Session = Depends(get_db), user: AdminUser = Depends(require_permission("cards.create"))):
    plan = db.get(Plan, payload.plan_id)
    if plan is None or not plan.is_active:
        raise HTTPException(status_code=404, detail="الباقة غير موجودة أو غير مفعلة")
    if db.query(Card.id).filter(Card.username == payload.username).first():
        raise HTTPException(status_code=409, detail="اسم المستخدم مستخدم من قبل")

    password = _credential_for(payload.card_type, payload.username, payload.password)
    point = (
        db.query(PointOfSale)
        .filter(PointOfSale.id == payload.point_of_sale_id)
        .with_for_update()
        .first()
        if payload.point_of_sale_id else None
    )
    if payload.point_of_sale_id and point is None:
        raise HTTPException(status_code=422, detail="اختر نقطة بيع موجودة ومفعلة")
    if not is_owner(user):
        assigned_ids = {item.id for item in user.point_of_sales}
        if point is None or point.id not in assigned_ids:
            raise HTTPException(status_code=403, detail="إنشاء الكروت مسموح فقط لنقاط البيع المرتبطة بحسابك")
    if point is not None:
        ensure_pos_card_creation_allowed(db, point)
    template = db.query(CardTemplate).filter(CardTemplate.code == payload.template_code).first() if payload.template_code else None
    if payload.template_code and template is None:
        raise HTTPException(status_code=404, detail="قالب الطباعة غير موجود")
    if template and template.plan_id is not None and template.plan_id != plan.id:
        raise HTTPException(status_code=422, detail="الباقة لا تطابق الباقة المرتبطة بقالب الطباعة")
    _ensure_encryption_ready()
    batch = CardBatch(
        batch_number="BAT" + secrets.token_hex(5).upper(),
        plan_id=plan.id,
        point_of_sale_id=point.id if point else None,
        template_code=payload.template_code,
        quantity=1,
        card_type=payload.card_type,
        generation_mode="single",
        username_length=len(payload.username),
        password_length=len(password),
        prefix="",
        requested_by=user.username,
    )
    try:
        db.add(batch)
        db.flush()
        card = _build_card(plan, payload.username, password, payload.card_type, payload.is_free, batch_id=batch.id)
        db.add(card)
        db.flush()
        db.add(CardEvent(
            card_id=card.id,
            event_type="created",
            details={"plan_id": plan.id, "is_free": payload.is_free, "card_type": payload.card_type, "batch_id": str(batch.id)},
            actor=user.username,
        ))
        record_audit(db, user, "card.created", "card", f"إنشاء كرت {card.username}", entity_id=card.id, details={"serial_number": card.serial_number, "plan_id": plan.id, "batch_number": batch.batch_number})
        db.commit()
        db.refresh(card)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="تعارض في بيانات الكرت؛ تحقق من اسم المستخدم وأعد المحاولة")

    return CardCreateResponse(
        id=card.id,
        batch_id=batch.id,
        batch_number=batch.batch_number,
        template_code=batch.template_code,
        point_of_sale_id=batch.point_of_sale_id,
        serial_number=card.serial_number,
        username=card.username,
        password=password,
        card_type=card.card_type,
        status=card.status,
        is_free=card.is_free,
    )


@router.post("/batch", response_model=CardBatchResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission("cards.create")), Depends(require_permission("cards.credentials"))])
def create_card_batch(payload: CardBatchCreate, db: Session = Depends(get_db), user: AdminUser = Depends(require_permission("cards.create"))):
    plan = db.get(Plan, payload.plan_id)
    if plan is None or not plan.is_active:
        raise HTTPException(status_code=404, detail="الباقة غير موجودة أو غير مفعلة")
    if payload.prefix and not (payload.prefix.isascii() and payload.prefix.isalnum()):
        raise HTTPException(status_code=422, detail="البادئة يجب أن تحتوي على حروف وأرقام فقط")
    if len(payload.prefix) >= payload.username_length:
        raise HTTPException(status_code=422, detail="طول البادئة يجب أن يكون أقل من طول اسم المستخدم")

    point = None
    if payload.point_of_sale_id is not None:
        point = (
            db.query(PointOfSale)
            .filter(PointOfSale.id == payload.point_of_sale_id)
            .with_for_update()
            .first()
        )
        if point is None:
            raise HTTPException(status_code=422, detail="اختر نقطة بيع موجودة ومفعلة")
        if not is_owner(user) and point.id not in {item.id for item in user.point_of_sales}:
            raise HTTPException(status_code=403, detail="إنشاء الكروت مسموح فقط لنقاط البيع المرتبطة بحسابك")
        ensure_pos_card_creation_allowed(db, point)
    elif not is_owner(user):
        raise HTTPException(status_code=403, detail="يجب ربط الكرت بنقطة بيع مسموح بها")
    template = None
    if payload.template_code:
        template = db.query(CardTemplate).filter(CardTemplate.code == payload.template_code).first()
        if template is None:
            raise HTTPException(status_code=404, detail="قالب الطباعة غير موجود")
        if template.plan_id is not None and template.plan_id != plan.id:
            raise HTTPException(status_code=422, detail="الباقة لا تطابق الباقة المرتبطة بقالب الطباعة")

    batch = None
    if payload.existing_batch_id is not None or payload.existing_batch_number is not None:
        batch_query = db.query(CardBatch).with_for_update()
        if payload.existing_batch_id is not None:
            batch_query = batch_query.filter(CardBatch.id == payload.existing_batch_id)
        if payload.existing_batch_number is not None:
            batch_query = batch_query.filter(
                func.lower(CardBatch.batch_number) == payload.existing_batch_number.strip().lower()
            )
        batch = batch_query.first()
        if batch is None:
            raise HTTPException(status_code=404, detail="لم يتم العثور على الدفعة السابقة بهذا الرقم")
        if (
            payload.existing_batch_id is not None
            and payload.existing_batch_number is not None
            and batch.batch_number.lower() != payload.existing_batch_number.strip().lower()
        ):
            raise HTTPException(status_code=409, detail="رقم الدفعة لا يطابق معرّف الدفعة المحدد")
        compatible = (
            batch.plan_id == plan.id
            and batch.point_of_sale_id == payload.point_of_sale_id
            and batch.template_code == payload.template_code
            and batch.card_type == payload.card_type
            and batch.generation_mode == payload.generation_mode
            and batch.username_length == payload.username_length
            and batch.password_length == payload.password_length
            and batch.prefix == payload.prefix
        )
        if not compatible:
            raise HTTPException(
                status_code=409,
                detail="لا يمكن ربط الكروت بهذه الدفعة؛ يجب تطابق الباقة والقالب ونقطة البيع ونوع الدخول وإعدادات التوليد",
            )

    _ensure_encryption_ready()
    existing: set[str] = set()
    credentials: list[tuple[str, str]] = []
    max_attempts = payload.quantity * 20
    attempts = 0

    while len(credentials) < payload.quantity and attempts < max_attempts:
        attempts += 1
        username = generate_username(payload.username_length, payload.generation_mode, payload.prefix)
        if username in existing:
            continue
        existing.add(username)
        credentials.append((username, ""))

    if len(credentials) != payload.quantity:
        raise HTTPException(status_code=503, detail="تعذر توليد أسماء فريدة؛ قلل حجم الدفعة أو غيّر الإعدادات")

    found = set(
        row[0] for row in db.execute(
            select(Card.username).where(Card.username.in_([username for username, _ in credentials]))
        ).all()
    )
    if found:
        raise HTTPException(status_code=409, detail="بعض الأسماء موجودة مسبقاً؛ أعد إنشاء الدفعة")

    cards: list[Card] = []
    response_cards: list[CardCreatedSecret] = []
    generated_passwords: list[str] = []
    is_new_batch = batch is None
    if is_new_batch:
        batch = CardBatch(
            batch_number="BAT" + secrets.token_hex(5).upper(),
            plan_id=plan.id,
            point_of_sale_id=point.id if point else None,
            template_code=payload.template_code,
            quantity=payload.quantity,
            card_type=payload.card_type,
            generation_mode=payload.generation_mode,
            username_length=payload.username_length,
            password_length=payload.password_length,
            prefix=payload.prefix,
            requested_by=user.username,
            is_online_sale=payload.is_online_sale,
            note=payload.note.strip() if payload.note else None,
        )
    else:
        batch.quantity += payload.quantity
        batch.is_online_sale = batch.is_online_sale or payload.is_online_sale
        if payload.note and payload.note.strip():
            batch.note = "\n".join(filter(None, [batch.note, payload.note.strip()]))
    try:
        if is_new_batch:
            db.add(batch)
            db.flush()
        for username, _ in credentials:
            if payload.card_type == "username_only":
                password = ""
            elif payload.card_type == "same_credentials":
                password = username
            else:
                password = generate_password(payload.password_length)

            card = _build_card(plan, username, password, payload.card_type, batch_id=batch.id)
            cards.append(card)
            generated_passwords.append(password)
        db.add_all(cards)
        db.flush()
        response_cards = [
            CardCreatedSecret(
                id=card.id,
                serial_number=card.serial_number,
                username=card.username,
                password=password,
            )
            for card, password in zip(cards, generated_passwords, strict=True)
        ]
        db.add_all([
            CardEvent(
                card_id=card.id,
                event_type="created",
                details={"plan_id": plan.id, "is_free": False, "card_type": payload.card_type, "batch": True, "batch_id": str(batch.id)},
                actor=user.username,
            )
            for card in cards
        ])
        record_audit(
            db,
            user,
            "cards.batch_created" if is_new_batch else "cards.batch_extended",
            "card_batch",
            f"{'إنشاء' if is_new_batch else 'إضافة كروت إلى'} دفعة {batch.batch_number}",
            entity_id=batch.id,
            details={
                "quantity_added": len(cards),
                "batch_quantity_total": batch.quantity,
                "plan_id": plan.id,
                "point_of_sale_id": batch.point_of_sale_id,
                "template_code": batch.template_code,
                "is_online_sale": batch.is_online_sale,
                "note": payload.note,
                "linked_existing_batch": not is_new_batch,
            },
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="حدث تعارض أثناء إنشاء الدفعة؛ لم يتم حفظ أي كرت")

    return CardBatchResponse(
        batch_id=batch.id,
        batch_number=batch.batch_number,
        plan_id=plan.id,
        template_code=batch.template_code,
        point_of_sale_id=batch.point_of_sale_id,
        is_online_sale=batch.is_online_sale,
        note=batch.note,
        created_count=len(response_cards),
        cards=response_cards,
    )
