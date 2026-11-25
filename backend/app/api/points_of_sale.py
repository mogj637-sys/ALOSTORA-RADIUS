from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_permission
from app.db.session import get_db
from app.models.auth import AdminUser
from app.models.core import Card, CardBatch, PointOfSale, PosAccountEntry, PosInventoryMovement, PrintJob, PrintJobItem
from app.services.audit import record_audit
from app.services.permissions import has_permission, is_owner
from app.schemas.points_of_sale import (
    PointOfSaleCreate,
    PointOfSaleInventoryResponse,
    PointOfSaleResponse,
    PointOfSaleOperationOption,
    PointOfSaleUpdate,
)

router = APIRouter(
    prefix="/api/v1/points-of-sale",
    tags=["points-of-sale"],
)


@router.get("", response_model=list[PointOfSaleResponse], dependencies=[Depends(require_permission("pos.view"))])
def list_points_of_sale(include_inactive: bool = False, db: Session = Depends(get_db), user: AdminUser = Depends(require_permission("pos.view"))):
    query = db.query(PointOfSale)
    if not any(role.code == "owner" for role in user.roles):
        assigned_ids = [point.id for point in user.point_of_sales]
        query = query.filter(PointOfSale.id.in_(assigned_ids)) if assigned_ids else query.filter(PointOfSale.id.is_(None))
    if not include_inactive:
        query = query.filter(PointOfSale.is_active.is_(True))
    return query.order_by(PointOfSale.id.desc()).all()



@router.get("/operation-options", response_model=list[PointOfSaleOperationOption])
def list_operation_options(
    operation: Literal["cards.create", "finance.create", "printing.create"] = Query(...),
    db: Session = Depends(get_db),
    user: AdminUser = Depends(get_current_user),
):
    if not has_permission(user, operation):
        raise HTTPException(status_code=403, detail="ليست لديك صلاحية تنفيذ هذه العملية")

    query = db.query(PointOfSale)
    if operation == "cards.create":
        query = query.filter(
            PointOfSale.is_active.is_(True),
            PointOfSale.allow_card_creation.is_(True),
        )
    elif operation == "printing.create":
        query = query.filter(
            PointOfSale.is_active.is_(True),
            PointOfSale.allow_printing.is_(True),
        )

    if not is_owner(user):
        assigned_ids = [point.id for point in user.point_of_sales]
        query = (
            query.filter(PointOfSale.id.in_(assigned_ids))
            if assigned_ids
            else query.filter(PointOfSale.id.is_(None))
        )

    return query.order_by(PointOfSale.id.desc()).all()


@router.post("", response_model=PointOfSaleResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission("pos.create"))])
def create_point_of_sale(payload: PointOfSaleCreate, db: Session = Depends(get_db), user: AdminUser = Depends(require_permission("pos.create"))):
    point = PointOfSale(**payload.model_dump())
    db.add(point)
    try:
        db.flush()
        record_audit(
            db,
            user,
            "pos.created",
            "point_of_sale",
            f"إنشاء نقطة بيع {point.name}",
            entity_id=point.id,
            details={
                "code": point.code,
                "is_active": point.is_active,
                "debt_limit": str(point.debt_limit) if point.debt_limit is not None else None,
                "allow_card_creation": point.allow_card_creation,
                "allow_printing": point.allow_printing,
            },
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="رمز نقطة البيع مستخدم من قبل")
    db.refresh(point)
    return point


@router.patch("/{point_id}", response_model=PointOfSaleResponse, dependencies=[Depends(require_permission("pos.update"))])
def update_point_of_sale(
    point_id: int,
    payload: PointOfSaleUpdate,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_permission("pos.update")),
):
    if not any(role.code == "owner" for role in user.roles) and point_id not in {point.id for point in user.point_of_sales}:
        raise HTTPException(status_code=403, detail="لا تملك صلاحية إدارة نقطة البيع هذه")
    point = db.get(PointOfSale, point_id)
    if point is None:
        raise HTTPException(status_code=404, detail="نقطة البيع غير موجودة")
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail="يجب إرسال حقل واحد على الأقل")
    protected_fields = {"is_active", "debt_limit", "allow_card_creation", "allow_printing"}
    if not is_owner(user) and protected_fields.intersection(changes):
        raise HTTPException(status_code=403, detail="تغيير سقف المديونية أو صلاحيات التشغيل أو إيقاف الحساب متاح لمدير النظام فقط")
    before = {key: getattr(point, key) for key in changes}
    for field, value in changes.items():
        setattr(point, field, value)
    record_audit(db, user, "pos.updated", "point_of_sale", f"تعديل نقطة بيع {point.name}", entity_id=point.id, details={"before": before, "after": changes})
    db.commit()
    db.refresh(point)
    return point


@router.delete("/{point_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_permission("pos.delete"))])
def delete_point_of_sale(
    point_id: int,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_permission("pos.delete")),
):
    point = db.query(PointOfSale).filter(PointOfSale.id == point_id).with_for_update().first()
    if point is None:
        raise HTTPException(status_code=404, detail="نقطة البيع غير موجودة")
    if not is_owner(user) and point.id not in {assigned.id for assigned in user.point_of_sales}:
        raise HTTPException(status_code=403, detail="لا تملك صلاحية حذف نقطة البيع هذه")
    if point.is_active:
        raise HTTPException(status_code=409, detail="أوقف نقطة البيع أولاً قبل حذفها")

    references = []
    checks = [
        ("كروت", db.query(Card.id).filter(Card.assigned_pos_id == point.id).first()),
        ("دفعات", db.query(CardBatch.id).filter(CardBatch.point_of_sale_id == point.id).first()),
        ("عمليات طباعة", db.query(PrintJob.id).filter(PrintJob.point_of_sale_id == point.id).first()),
        ("حركات المخزون", db.query(PosInventoryMovement.id).filter(PosInventoryMovement.point_of_sale_id == point.id).first()),
        ("قيود مالية", db.query(PosAccountEntry.id).filter(PosAccountEntry.point_of_sale_id == point.id).first()),
        (
            "تخصيصات حسابات الإدارة",
            db.query(AdminUser.id)
            .filter(
                AdminUser.id != user.id,
                AdminUser.point_of_sales.any(PointOfSale.id == point.id),
            )
            .first(),
        ),
    ]
    references.extend(label for label, result in checks if result is not None)
    if references:
        raise HTTPException(
            status_code=409,
            detail="لا يمكن حذف نقطة البيع لارتباطها بسجلات محفوظة: " + "، ".join(references),
        )

    record_audit(
        db,
        user,
        "pos.deleted",
        "point_of_sale",
        f"حذف نقطة البيع {point.name}",
        entity_id=point.id,
        details={"code": point.code, "name": point.name},
    )
    db.delete(point)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="لا يمكن حذف نقطة البيع لارتباطها بسجلات أخرى")
    return None


@router.get("/{point_id}/inventory", response_model=PointOfSaleInventoryResponse)
def point_of_sale_inventory(point_id: int, db: Session = Depends(get_db), user: AdminUser = Depends(require_permission("pos.view"))):
    if not any(role.code == "owner" for role in user.roles) and point_id not in {point.id for point in user.point_of_sales}:
        raise HTTPException(status_code=403, detail="لا تملك صلاحية الاطلاع على مخزون نقطة البيع هذه")
    point = db.get(PointOfSale, point_id)
    if point is None:
        raise HTTPException(status_code=404, detail="نقطة البيع غير موجودة")

    allocated = db.query(func.count(Card.id)).filter(
        Card.assigned_pos_id == point_id,
    ).scalar() or 0
    used = db.query(func.count(Card.id)).filter(
        Card.assigned_pos_id == point_id,
        Card.first_used_at.is_not(None),
    ).scalar() or 0
    suspended = db.query(func.count(Card.id)).filter(
        Card.assigned_pos_id == point_id,
        Card.status == "suspended",
    ).scalar() or 0
    printed_value = db.query(func.coalesce(func.sum(Card.price_snapshot), 0)).filter(
        Card.assigned_pos_id == point_id,
        Card.is_free.is_(False),
    ).scalar() or Decimal("0.00")
    free_printed = (
        db.query(func.count(PrintJobItem.id))
        .join(PrintJob, PrintJob.id == PrintJobItem.print_job_id)
        .filter(
            PrintJob.point_of_sale_id == point_id,
            PrintJob.is_reprint.is_(False),
            PrintJobItem.is_free.is_(True),
        )
        .scalar() or 0
    )
    return PointOfSaleInventoryResponse(
        point_of_sale_id=point.id,
        point_of_sale_name=point.name,
        allocated_cards=allocated,
        used_cards=used,
        suspended_cards=suspended,
        commercial_printed_value=printed_value,
        free_cards_printed=free_printed,
    )
