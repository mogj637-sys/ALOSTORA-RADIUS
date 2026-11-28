from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from app.api.deps import get_current_user, require_permission
from app.db.session import get_db
from app.models.auth import AdminUser
from app.models.core import PointOfSale, PosAccountEntry
from app.services.audit import record_audit
from app.services.permissions import has_permission, is_owner
from app.schemas.pos_accounts import (
    PosAccountEntryCreate,
    PosAccountEntryOperationOption,
    PosAccountEntryResponse,
    PosAccountEntryReverse,
    PosAccountEntryUpdate,
    PosAccountSummaryResponse,
)

router = APIRouter(
    prefix="/api/v1/points-of-sale/{point_id}/account",
    tags=["point-of-sale-accounting"],
)


def _require_point_access(point_id: int, db: Session, user: AdminUser) -> PointOfSale:
    if not is_owner(user) and point_id not in {point.id for point in user.point_of_sales}:
        raise HTTPException(status_code=403, detail="لا تملك صلاحية إدارة حساب نقطة البيع هذه")
    point = db.get(PointOfSale, point_id)
    if point is None:
        raise HTTPException(status_code=404, detail="نقطة البيع غير موجودة")
    return point


def _entry_response_data(entry: PosAccountEntry, reversed_by_id: int | None = None) -> dict:
    return {
        "id": entry.id,
        "point_of_sale_id": entry.point_of_sale_id,
        "entry_type": entry.entry_type,
        "direction": entry.direction,
        "amount": entry.amount,
        "description": entry.description,
        "reference": entry.reference,
        "idempotency_key": entry.idempotency_key,
        "created_by": entry.created_by,
        "created_at": entry.created_at,
        "reversal_of_id": entry.reversal_of_id,
        "reversed_by_id": reversed_by_id,
    }


def _reversed_by_id(db: Session, entry_id: int) -> int | None:
    return db.query(PosAccountEntry.id).filter(
        PosAccountEntry.reversal_of_id == entry_id
    ).scalar()


def _entry_operation_data(entry: PosAccountEntry, reversed_by_id: int | None = None) -> dict:
    return {
        "id": entry.id,
        "point_of_sale_id": entry.point_of_sale_id,
        "entry_type": entry.entry_type,
        "direction": entry.direction,
        "amount": entry.amount,
        "description": entry.description,
        "reference": entry.reference,
        "created_at": entry.created_at,
        "reversal_of_id": entry.reversal_of_id,
        "reversed_by_id": reversed_by_id,
    }


@router.get(
    "",
    response_model=PosAccountSummaryResponse,
    dependencies=[Depends(require_permission("finance.view"))],
)
def account_summary(
    point_id: int,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_permission("finance.view")),
):
    point = _require_point_access(point_id, db, user)
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


@router.get(
    "/entries",
    response_model=list[PosAccountEntryResponse],
    dependencies=[Depends(require_permission("finance.view"))],
)
def list_account_entries(
    point_id: int,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_permission("finance.view")),
):
    _require_point_access(point_id, db, user)
    reversal = aliased(PosAccountEntry)
    rows = (
        db.query(PosAccountEntry, reversal.id.label("reversed_by_id"))
        .outerjoin(reversal, reversal.reversal_of_id == PosAccountEntry.id)
        .filter(PosAccountEntry.point_of_sale_id == point_id)
        .order_by(PosAccountEntry.created_at.desc(), PosAccountEntry.id.desc())
        .limit(limit)
        .all()
    )
    return [_entry_response_data(entry, reversed_by_id) for entry, reversed_by_id in rows]


@router.get("/entries/operation-options", response_model=list[PosAccountEntryOperationOption])
def list_entry_operation_options(
    point_id: int,
    operation: Literal["finance.update", "finance.delete"] = Query(...),
    query: str = Query(..., min_length=2, max_length=120),
    db: Session = Depends(get_db),
    user: AdminUser = Depends(get_current_user),
):
    if not has_permission(user, operation):
        raise HTTPException(status_code=403, detail="ليست لديك صلاحية تنفيذ هذه العملية")
    _require_point_access(point_id, db, user)

    normalized = query.strip()
    if len(normalized) < 2:
        raise HTTPException(status_code=422, detail="اكتب حرفين على الأقل للبحث عن الحركة المالية")
    escaped = normalized.replace("!", "!!").replace("%", "!%").replace("_", "!_")
    pattern = f"%{escaped}%"
    conditions = [
        PosAccountEntry.description.ilike(pattern, escape="!"),
        PosAccountEntry.reference.ilike(pattern, escape="!"),
    ]
    if normalized.isdigit() and len(normalized) <= 18:
        conditions.append(PosAccountEntry.id == int(normalized))

    reversal = aliased(PosAccountEntry)
    rows = (
        db.query(PosAccountEntry, reversal.id.label("reversed_by_id"))
        .outerjoin(reversal, reversal.reversal_of_id == PosAccountEntry.id)
        .filter(
            PosAccountEntry.point_of_sale_id == point_id,
            or_(*conditions),
        )
        .order_by(PosAccountEntry.created_at.desc(), PosAccountEntry.id.desc())
        .limit(20)
        .all()
    )
    return [
        {
            "id": entry.id,
            "point_of_sale_id": entry.point_of_sale_id,
            "entry_type": entry.entry_type,
            "direction": entry.direction,
            "amount": entry.amount,
            "description": entry.description,
            "reference": entry.reference,
            "created_at": entry.created_at,
            "reversal_of_id": entry.reversal_of_id,
            "reversed_by_id": reversed_by_id,
        }
        for entry, reversed_by_id in rows
    ]


@router.post(
    "/entries",
    response_model=PosAccountEntryResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("finance.create"))],
)
def create_account_entry(
    point_id: int,
    payload: PosAccountEntryCreate,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_permission("finance.create")),
):
    point = _require_point_access(point_id, db, user)
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
        return _entry_response_data(existing, _reversed_by_id(db, existing.id))

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
        record_audit(
            db,
            user,
            "finance.entry_created",
            "pos_account_entry",
            f"تسجيل حركة مالية لنقطة البيع {point.name}",
            entity_id=entry.id,
            details={
                "entry_type": entry.entry_type,
                "direction": entry.direction,
                "amount": str(entry.amount),
                "reference": entry.reference,
            },
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.query(PosAccountEntry).filter(
            PosAccountEntry.idempotency_key == payload.idempotency_key
        ).first()
        if existing and (
            existing.point_of_sale_id == point_id
            and existing.entry_type == payload.entry_type
            and existing.direction == payload.direction
            and existing.amount == payload.amount
            and existing.description == payload.description
            and existing.reference == payload.reference
        ):
            return _entry_response_data(existing, _reversed_by_id(db, existing.id))
        raise HTTPException(status_code=409, detail="تعارض في تسجيل الحركة المالية")
    db.refresh(entry)
    return _entry_response_data(entry)


@router.patch(
    "/entries/{entry_id}",
    response_model=PosAccountEntryOperationOption,
    dependencies=[Depends(require_permission("finance.update"))],
)
def update_account_entry(
    point_id: int,
    entry_id: int,
    payload: PosAccountEntryUpdate,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_permission("finance.update")),
):
    _require_point_access(point_id, db, user)
    entry = (
        db.query(PosAccountEntry)
        .filter(
            PosAccountEntry.id == entry_id,
            PosAccountEntry.point_of_sale_id == point_id,
        )
        .with_for_update()
        .first()
    )
    if entry is None:
        raise HTTPException(status_code=404, detail="الحركة المالية غير موجودة")
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail="حدد البيان أو الرقم المرجعي لتعديله")
    before = {"description": entry.description, "reference": entry.reference}
    for field, value in changes.items():
        setattr(entry, field, value)
    after = {"description": entry.description, "reference": entry.reference}
    record_audit(
        db,
        user,
        "finance.entry_metadata_updated",
        "pos_account_entry",
        f"تعديل بيانات الحركة المالية رقم {entry.id}",
        entity_id=entry.id,
        details={"before": before, "after": after},
    )
    db.commit()
    db.refresh(entry)
    return _entry_operation_data(entry, _reversed_by_id(db, entry.id))


@router.post(
    "/entries/{entry_id}/reverse",
    response_model=PosAccountEntryOperationOption,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("finance.delete"))],
)
def reverse_account_entry(
    point_id: int,
    entry_id: int,
    payload: PosAccountEntryReverse,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_permission("finance.delete")),
):
    point = _require_point_access(point_id, db, user)
    entry = (
        db.query(PosAccountEntry)
        .filter(
            PosAccountEntry.id == entry_id,
            PosAccountEntry.point_of_sale_id == point_id,
        )
        .with_for_update()
        .first()
    )
    if entry is None:
        raise HTTPException(status_code=404, detail="الحركة المالية غير موجودة")

    reason = payload.reason.strip() if payload.reason else ""
    description = f"عكس الحركة رقم {entry.id}"
    if reason:
        description = f"{description}: {reason}"

    existing_key = db.query(PosAccountEntry).filter(
        PosAccountEntry.idempotency_key == payload.idempotency_key
    ).first()
    if existing_key is not None:
        same_replay = (
            existing_key.reversal_of_id == entry.id
            and existing_key.description == description[:500]
            and existing_key.entry_type == entry.entry_type
            and existing_key.direction == ("credit" if entry.direction == "debit" else "debit")
            and existing_key.amount == entry.amount
        )
        if same_replay:
            return _entry_operation_data(existing_key)
        raise HTTPException(status_code=409, detail="مفتاح العكس مستخدم لطلب مختلف")

    if entry.reversal_of_id is not None:
        raise HTTPException(status_code=409, detail="لا يمكن عكس قيد عكس سابق")
    existing_reversal = db.query(PosAccountEntry).filter(
        PosAccountEntry.reversal_of_id == entry.id
    ).first()
    if existing_reversal is not None:
        raise HTTPException(status_code=409, detail="تم عكس هذه الحركة مسبقاً")

    reversal = PosAccountEntry(
        point_of_sale_id=point_id,
        entry_type=entry.entry_type,
        direction="credit" if entry.direction == "debit" else "debit",
        amount=entry.amount,
        description=description[:500],
        reference=entry.reference,
        idempotency_key=payload.idempotency_key,
        created_by=user.username,
        reversal_of_id=entry.id,
    )
    db.add(reversal)
    try:
        db.flush()
        record_audit(
            db,
            user,
            "finance.entry_reversed",
            "pos_account_entry",
            f"عكس الحركة المالية رقم {entry.id}",
            entity_id=reversal.id,
            details={
                "original_entry_id": entry.id,
                "reversal_entry_id": reversal.id,
                "entry_type": entry.entry_type,
                "original_direction": entry.direction,
                "reversal_direction": reversal.direction,
                "amount": str(entry.amount),
                "reason": reason or None,
            },
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.query(PosAccountEntry).filter(
            PosAccountEntry.idempotency_key == payload.idempotency_key
        ).first()
        if (
            existing is not None
            and existing.reversal_of_id == entry_id
            and existing.description == description[:500]
        ):
            return _entry_operation_data(existing)
        raise HTTPException(status_code=409, detail="تعارض: تم عكس الحركة أو استخدام مفتاح العكس مسبقاً")
    db.refresh(reversal)
    return _entry_operation_data(reversal)
