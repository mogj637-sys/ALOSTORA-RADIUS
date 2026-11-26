from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_permission
from app.db.session import get_db
from app.models.auth import AdminUser
from app.models.core import Card, CardBatch, CardTemplate, Plan
from app.services.audit import record_audit
from app.services.permissions import has_permission
from app.schemas.plans import PlanCreate, PlanOperationOption, PlanResponse, PlanUpdate

router = APIRouter(prefix="/api/v1/plans", tags=["plans"])


@router.get("", response_model=list[PlanResponse], dependencies=[Depends(require_permission("plans.view"))])
def list_plans(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
):
    query = db.query(Plan)
    if not include_inactive:
        query = query.filter(Plan.is_active.is_(True))
    return query.order_by(Plan.id.desc()).all()


@router.post("", response_model=PlanResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission("plans.create"))])
def create_plan(payload: PlanCreate, db: Session = Depends(get_db), user: AdminUser = Depends(require_permission("plans.create"))):
    plan = Plan(**payload.model_dump())
    db.add(plan)
    try:
        db.flush()
        record_audit(db, user, "plan.created", "plan", f"إنشاء باقة {plan.name}", entity_id=plan.id, details={"code": plan.code, "price": str(plan.price), "is_active": plan.is_active})
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="رمز الباقة مستخدم من قبل")
    db.refresh(plan)
    return plan


@router.get("/operation-options", response_model=list[PlanOperationOption])
def plan_operation_options(
    operation: Literal["update", "delete"],
    q: str = Query(..., min_length=2, max_length=80),
    db: Session = Depends(get_db),
    user: AdminUser = Depends(get_current_user),
):
    permission_code = f"plans.{operation}"
    if not has_permission(user, permission_code):
        raise HTTPException(status_code=403, detail=f"ليست لديك صلاحية تنفيذ هذه العملية ({permission_code})")

    normalized = q.strip()
    if len(normalized) < 2:
        raise HTTPException(status_code=422, detail="اكتب حرفين على الأقل للبحث عن باقة")
    escaped = normalized.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    pattern = f"%{escaped}%"
    return (
        db.query(Plan)
        .filter(or_(Plan.code.ilike(pattern, escape="\\"), Plan.name.ilike(pattern, escape="\\")))
        .order_by(Plan.id.desc())
        .limit(20)
        .all()
    )


@router.get("/{plan_id}/edit", response_model=PlanResponse, dependencies=[Depends(require_permission("plans.update"))])
def get_plan_for_update(plan_id: int, db: Session = Depends(get_db)):
    plan = db.get(Plan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="الباقة غير موجودة")
    return plan


@router.patch("/{plan_id}", response_model=PlanResponse, dependencies=[Depends(require_permission("plans.update"))])
def update_plan(plan_id: int, payload: PlanUpdate, db: Session = Depends(get_db), user: AdminUser = Depends(require_permission("plans.update"))):
    plan = db.get(Plan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="الباقة غير موجودة")

    updates = payload.model_dump(exclude_unset=True)
    before = {key: str(getattr(plan, key)) if getattr(plan, key) is not None else None for key in updates}
    next_price = updates.get("price", plan.price)
    next_type = updates.get("commission_type", plan.commission_type)
    next_value = updates.get("commission_value", plan.commission_value)
    if next_type == "fixed" and next_value > next_price:
        raise HTTPException(status_code=422, detail="العمولة الثابتة لا يمكن أن تتجاوز سعر الباقة")
    if next_type == "none":
        updates["commission_value"] = 0
    for field, value in updates.items():
        setattr(plan, field, value)

    try:
        record_audit(db, user, "plan.updated", "plan", f"تعديل باقة {plan.name}", entity_id=plan.id, details={"before": before, "changed_fields": list(updates.keys())})
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="رمز الباقة مستخدم من قبل")
    db.refresh(plan)
    return plan

@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_permission("plans.delete"))])
def delete_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_permission("plans.delete")),
):
    plan = db.query(Plan).filter(Plan.id == plan_id).with_for_update().first()
    if plan is None:
        raise HTTPException(status_code=404, detail="الباقة غير موجودة")
    if plan.is_active:
        raise HTTPException(status_code=409, detail="أوقف الباقة أولاً قبل حذفها")

    references = []
    if db.query(Card.id).filter(Card.plan_id == plan.id).first() is not None:
        references.append("كروت")
    if db.query(CardBatch.id).filter(CardBatch.plan_id == plan.id).first() is not None:
        references.append("دفعات")
    if db.query(CardTemplate.id).filter(CardTemplate.plan_id == plan.id).first() is not None:
        references.append("قوالب")

    if references:
        raise HTTPException(
            status_code=409,
            detail="لا يمكن حذف الباقة لأنها مرتبطة بسجلات محفوظة: " + "، ".join(references),
        )

    record_audit(
        db, user, "plan.deleted", "plan",
        f"حذف الباقة {plan.name}", entity_id=plan.id,
        details={"code": plan.code, "name": plan.name},
    )
    db.delete(plan)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="لا يمكن حذف الباقة لارتباطها بسجلات أخرى")
    return None
