from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, case
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.auth import AdminUser
from app.models.core import PointOfSale, PosAccountEntry
from app.services.audit import record_audit
from app.schemas.pos_accounts import (
    PosAccountEntryCreate,
    PosAccountEntryResponse,
    PosAccountSummaryResponse,
)

router = APIRouter(
    prefix="/api/v1/points-of-sale/{point_id}/account",
    tags=["point-of-sale-accounting"],
    dependencies=[Depends(require_permission("finance.view"))],
)


@router.get("", response_model=PosAccountSummaryResponse)
def account_summary(point_id: int, db: Session = Depends(get_db)):
    if not any(role.code == "owner" for role in user.roles) and point_id not in {point.id for point in user.point_of_sales}:
        raise HTTPException(status_code=403, detail="لا تملك صلاحية إدارة حساب نقطة البيع هذه")
    point = db.get(PointOfSale, point_id)
    if point is None:
        raise HTTPException(status_code=404, detail="نقطة البيع غير موجودة")
    debit, credit = db.query(
        func.coalesce(func.sum(case((PosAccountEntry.direction == "debit", PosAccountEntry.amount), else_=0)), 0),
        func.coalesce(func.sum(case((PosAccountEntry.direction == "credit", PosAccountEntry.amount), else_=0)), 0),
    ).filter(PosAccountEntry.point_of_sale_id == point_id).one()
    return PosAccountSummaryResponse(
        point_of_sale_id=point.id,
        point_of_sale_name=point.name,
        total_debit=debit,
        total_credit=credit,
        balance_due=Decimal(debit) - Decimal(credit),
    )


@router.get("/entries", response_model=list[PosAccountEntryResponse])
def list_account_entries(
    point_id: int,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_permission("finance.view")),
):
    if not any(role.code == "owner" for role in user.roles) and point_id not in {point.id for point in user.point_of_sales}:
        raise HTTPException(status_code=403, detail="لا تملك صلاحية الاطلاع على حساب نقطة البيع هذه")
    if db.get(PointOfSale, point_id) is None:
        raise HTTPException(status_code=404, detail="نقطة البيع غير موجودة")
    return (
        db.query(PosAccountEntry)
        .filter(PosAccountEntry.point_of_sale_id == point_id)
        .order_by(PosAccountEntry.created_at.desc(), PosAccountEntry.id.desc())
        .limit(limit)
        .all()
    )


@router.post("/entries", response_model=PosAccountEntryResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission("finance.manage"))])
def create_account_entry(
    point_id: int,
    payload: PosAccountEntryCreate,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_permission("finance.manage")),
):
    point = db.get(PointOfSale, point_id)
    if point is None:
        raise HTTPException(status_code=404, detail="نقطة البيع غير موجودة")
    existing = db.query(PosAccountEntry).filter(
        PosAccountEntry.idempotency_key == payload.idempotency_key
    ).first()
    if existing:
        same = (
            existing.point_of_sale_id == point_id
            and existing.entry_type == payload.entry_type
            and existing.direction == payload.direction
            and existing.amount == payload.amount
            and existing.description == payload.description
            and existing.reference == payload.reference
        )
        if not same:
            raise HTTPException(status_code=409, detail="مفتاح الحركة مستخدم لعملية مالية مختلفة")
        return existing

    entry = PosAccountEntry(
        point_of_sale_id=point_id,
        entry_type=payload.entry_type,
        direction=payload.direction,
        amount=payload.amount,
        description=payload.description,
        reference=payload.reference,
        idempotency_key=payload.idempotency_key,
        created_by=user.username,
    )
    db.add(entry)
    try:
        db.flush()
        record_audit(db, user, "finance.entry_created", "pos_account_entry", f"تسجيل حركة مالية لنقطة البيع {point.name}", entity_id=entry.id, details={"entry_type": entry.entry_type, "direction": entry.direction, "amount": str(entry.amount), "reference": entry.reference})
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.query(PosAccountEntry).filter(
            PosAccountEntry.idempotency_key == payload.idempotency_key
        ).first()
        if existing and existing.point_of_sale_id == point_id and existing.entry_type == payload.entry_type and existing.direction == payload.direction and existing.amount == payload.amount and existing.description == payload.description and existing.reference == payload.reference:
            return existing
        raise HTTPException(status_code=409, detail="تعارض في تسجيل الحركة المالية")
    db.refresh(entry)
    return entry
