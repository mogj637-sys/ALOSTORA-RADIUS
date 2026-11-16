from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.auth import AdminUser
from app.models.core import Card, PointOfSale, PrintJob, PrintJobItem
from app.services.audit import record_audit
from app.schemas.points_of_sale import (
    PointOfSaleCreate,
    PointOfSaleInventoryResponse,
    PointOfSaleResponse,
    PointOfSaleUpdate,
)

router = APIRouter(
    prefix="/api/v1/points-of-sale",
    tags=["points-of-sale"],
    dependencies=[Depends(require_permission("pos.view"))],
)


@router.get("", response_model=list[PointOfSaleResponse])
def list_points_of_sale(include_inactive: bool = False, db: Session = Depends(get_db)):
    query = db.query(PointOfSale)
    if not include_inactive:
        query = query.filter(PointOfSale.is_active.is_(True))
    return query.order_by(PointOfSale.id.desc()).all()


@router.post("", response_model=PointOfSaleResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission("pos.manage"))])
def create_point_of_sale(payload: PointOfSaleCreate, db: Session = Depends(get_db), user: AdminUser = Depends(require_permission("pos.manage"))):
    point = PointOfSale(**payload.model_dump())
    db.add(point)
    try:
        db.flush()
        record_audit(db, user, "pos.created", "point_of_sale", f"إنشاء نقطة بيع {point.name}", entity_id=point.id, details={"code": point.code, "is_active": point.is_active})
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="رمز نقطة البيع مستخدم من قبل")
    db.refresh(point)
    return point


@router.patch("/{point_id}", response_model=PointOfSaleResponse, dependencies=[Depends(require_permission("pos.manage"))])
def update_point_of_sale(
    point_id: int,
    payload: PointOfSaleUpdate,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_permission("pos.manage")),
):
    point = db.get(PointOfSale, point_id)
    if point is None:
        raise HTTPException(status_code=404, detail="نقطة البيع غير موجودة")
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail="يجب إرسال حقل واحد على الأقل")
    before = {key: getattr(point, key) for key in changes}
    for field, value in changes.items():
        setattr(point, field, value)
    record_audit(db, user, "pos.updated", "point_of_sale", f"تعديل نقطة بيع {point.name}", entity_id=point.id, details={"before": before, "after": changes})
    db.commit()
    db.refresh(point)
    return point


@router.get("/{point_id}/inventory", response_model=PointOfSaleInventoryResponse)
def point_of_sale_inventory(point_id: int, db: Session = Depends(get_db)):
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
