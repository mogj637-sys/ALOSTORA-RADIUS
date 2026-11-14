import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_owner
from app.db.session import get_db
from app.models.core import Card, CardEvent, Plan
from app.schemas.cards import (
    CardBatchCreate,
    CardBatchResponse,
    CardCreatedSecret,
    CardCreateResponse,
    CardListItem,
    CardSingleCreate,
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


def _build_card(plan: Plan, username: str, password: str, card_type: str, is_free: bool = False) -> Card:
    return Card(
        serial_number=_new_serial(),
        username=username,
        credential_ciphertext=encrypt_credential(password),
        credential_scheme="fernet_v1",
        card_type=card_type,
        status="generated",
        is_free=is_free,
        plan_id=plan.id,
        plan_snapshot=_plan_snapshot(plan),
        price_snapshot=0 if is_free else plan.price,
    )


@router.get("", response_model=list[CardListItem])
def list_cards(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
):
    query = db.query(Card)
    if status_filter:
        query = query.filter(Card.status == status_filter)
    return query.order_by(Card.created_at.desc()).offset(offset).limit(limit).all()


@router.post("/single", response_model=CardCreateResponse, status_code=status.HTTP_201_CREATED)
def create_single_card(payload: CardSingleCreate, db: Session = Depends(get_db)):
    plan = db.get(Plan, payload.plan_id)
    if plan is None or not plan.is_active:
        raise HTTPException(status_code=404, detail="الباقة غير موجودة أو غير مفعلة")
    if db.query(Card.id).filter(Card.username == payload.username).first():
        raise HTTPException(status_code=409, detail="اسم المستخدم مستخدم من قبل")

    password = _credential_for(payload.card_type, payload.username, payload.password)
    _ensure_encryption_ready()
    try:
        card = _build_card(plan, payload.username, password, payload.card_type, payload.is_free)
        db.add(card)
        db.flush()
        db.add(CardEvent(
            card_id=card.id,
            event_type="created",
            details={"plan_id": plan.id, "is_free": payload.is_free, "card_type": payload.card_type},
            actor="admin",
        ))
        db.commit()
        db.refresh(card)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="تعارض في بيانات الكرت؛ تحقق من اسم المستخدم وأعد المحاولة")

    return CardCreateResponse(
        id=card.id,
        serial_number=card.serial_number,
        username=card.username,
        password=password,
        card_type=card.card_type,
        status=card.status,
        is_free=card.is_free,
    )


@router.post("/batch", response_model=CardBatchResponse, status_code=status.HTTP_201_CREATED)
def create_card_batch(payload: CardBatchCreate, db: Session = Depends(get_db)):
    plan = db.get(Plan, payload.plan_id)
    if plan is None or not plan.is_active:
        raise HTTPException(status_code=404, detail="الباقة غير موجودة أو غير مفعلة")
    if payload.prefix and not payload.prefix.isalnum():
        raise HTTPException(status_code=422, detail="البادئة يجب أن تحتوي على حروف وأرقام فقط")
    if len(payload.prefix) >= payload.username_length:
        raise HTTPException(status_code=422, detail="طول البادئة يجب أن يكون أقل من طول اسم المستخدم")

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
    try:
        for username, _ in credentials:
            if payload.card_type == "username_only":
                password = ""
            elif payload.card_type == "same_credentials":
                password = username
            else:
                password = generate_password(payload.password_length)

            card = _build_card(plan, username, password, payload.card_type)
            cards.append(card)
            response_cards.append(CardCreatedSecret(
                serial_number=card.serial_number,
                username=username,
                password=password,
            ))

        db.add_all(cards)
        db.flush()
        db.add_all([
            CardEvent(
                card_id=card.id,
                event_type="created",
                details={"plan_id": plan.id, "is_free": False, "card_type": payload.card_type, "batch": True},
                actor="admin",
            )
            for card in cards
        ])
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="حدث تعارض أثناء إنشاء الدفعة؛ لم يتم حفظ أي كرت")

    return CardBatchResponse(created_count=len(response_cards), cards=response_cards)
