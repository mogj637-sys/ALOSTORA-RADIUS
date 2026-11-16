from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.auth import AdminUser
from app.models.core import Plan
from app.services.audit import record_audit
from app.schemas.plans import PlanCreate, PlanResponse, PlanUpdate

router = APIRouter(prefix="/api/v1/plans", tags=["plans"], dependencies=[Depends(require_permission("plans.view"))])


@router.get("", response_model=list[PlanResponse])
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


@router.patch("/{plan_id}", response_model=PlanResponse, dependencies=[Depends(require_permission("plans.create"))])
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
