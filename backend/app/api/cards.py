import secrets

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_owner
from app.db.session import get_db
from app.models.auth import AdminUser
from app.models.core import Card, CardBatch, CardEvent, CardTemplate, Plan, PointOfSale, RadiusSession
from app.services.radius_disconnect import send_disconnect_for_session
from app.schemas.cards import (
    CardBatchCreate,
    CardBatchResponse,
    CardBatchListItem,
    CardCreatedSecret,
    CardCreateResponse,
    CardListItem,
    CardSingleCreate,
    CardStatusUpdate,
)
from app.services.card_generator import generate_password, generate_username
from app.services.credentials import CredentialEncryptionNotConfigured, encrypt_credential

router = APIRouter(prefix="/api/v1/cards", tags=["cards"], dependencies=[Depends(get_current_owner)])


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
):
    rows = (
        db.query(CardBatch, Plan, PointOfSale)
        .join(Plan, Plan.id == CardBatch.plan_id)
        .outerjoin(PointOfSale, PointOfSale.id == CardBatch.point_of_sale_id)
        .order_by(CardBatch.created_at.desc())
        .limit(limit)
        .all()
    )
    results = []
    for batch, plan, point in rows:
        printed = db.query(func.count(Card.id)).filter(
            Card.batch_id == batch.id,
            Card.status.in_(["allocated", "printed_free", "active", "expired", "exhausted"]),
        ).scalar() or 0
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
            created_at=batch.created_at,
            printed_count=printed,
        ))
    return results


@router.get("", response_model=list[CardListItem])
def list_cards(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    status_filter: str | None = Query(default=None, alias="status"),
    search: str | None = Query(default=None, min_length=1, max_length=120),
    plan_id: int | None = Query(default=None, gt=0),
    is_free: bool | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(Card)
    if status_filter:
        query = query.filter(Card.status == status_filter)
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(Card.username.ilike(term), Card.serial_number.ilike(term))
        )
    if plan_id is not None:
        query = query.filter(Card.plan_id == plan_id)
    if is_free is not None:
        query = query.filter(Card.is_free.is_(is_free))
    return query.order_by(Card.created_at.desc()).offset(offset).limit(limit).all()


@router.patch("/{card_id}/status", response_model=CardListItem)
def update_card_status(
    card_id: str,
    payload: CardStatusUpdate,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(get_current_owner),
):
    from uuid import UUID

    try:
        card_uuid = UUID(card_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="معرّف الكرت غير صالح")

    card = db.query(Card).filter(Card.id == card_uuid).with_for_update().first()
    if card is None:
        raise HTTPException(status_code=404, detail="الكرت غير موجود")

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


@router.post("/single", response_model=CardCreateResponse, status_code=status.HTTP_201_CREATED)
def create_single_card(payload: CardSingleCreate, db: Session = Depends(get_db), user: AdminUser = Depends(get_current_owner)):
    plan = db.get(Plan, payload.plan_id)
    if plan is None or not plan.is_active:
        raise HTTPException(status_code=404, detail="الباقة غير موجودة أو غير مفعلة")
    if db.query(Card.id).filter(Card.username == payload.username).first():
        raise HTTPException(status_code=409, detail="اسم المستخدم مستخدم من قبل")

    password = _credential_for(payload.card_type, payload.username, payload.password)
    point = db.get(PointOfSale, payload.point_of_sale_id) if payload.point_of_sale_id else None
    if payload.point_of_sale_id and (point is None or not point.is_active):
        raise HTTPException(status_code=422, detail="اختر نقطة بيع موجودة ومفعلة")
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


@router.post("/batch", response_model=CardBatchResponse, status_code=status.HTTP_201_CREATED)
def create_card_batch(payload: CardBatchCreate, db: Session = Depends(get_db), user: AdminUser = Depends(get_current_owner)):
    plan = db.get(Plan, payload.plan_id)
    if plan is None or not plan.is_active:
        raise HTTPException(status_code=404, detail="الباقة غير موجودة أو غير مفعلة")
    if payload.prefix and not (payload.prefix.isascii() and payload.prefix.isalnum()):
        raise HTTPException(status_code=422, detail="البادئة يجب أن تحتوي على حروف وأرقام فقط")
    if len(payload.prefix) >= payload.username_length:
        raise HTTPException(status_code=422, detail="طول البادئة يجب أن يكون أقل من طول اسم المستخدم")

    point = None
    if payload.point_of_sale_id is not None:
        point = db.get(PointOfSale, payload.point_of_sale_id)
        if point is None or not point.is_active:
            raise HTTPException(status_code=422, detail="اختر نقطة بيع موجودة ومفعلة")
    template = None
    if payload.template_code:
        template = db.query(CardTemplate).filter(CardTemplate.code == payload.template_code).first()
        if template is None:
            raise HTTPException(status_code=404, detail="قالب الطباعة غير موجود")
        if template.plan_id is not None and template.plan_id != plan.id:
            raise HTTPException(status_code=422, detail="الباقة لا تطابق الباقة المرتبطة بقالب الطباعة")

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
    )
    try:
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
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="حدث تعارض أثناء إنشاء الدفعة؛ لم يتم حفظ أي كرت")

    return CardBatchResponse(batch_id=batch.id, batch_number=batch.batch_number, plan_id=plan.id, template_code=batch.template_code, point_of_sale_id=batch.point_of_sale_id, created_count=len(response_cards), cards=response_cards)
