from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_owner
from app.db.session import get_db
from app.models.core import Plan
from app.schemas.plans import PlanCreate, PlanResponse, PlanUpdate

router = APIRouter(prefix="/api/v1/plans", tags=["plans"], dependencies=[Depends(get_current_owner)])


@router.get("", response_model=list[PlanResponse])
def list_plans(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
):
    query = db.query(Plan)
    if not include_inactive:
        query = query.filter(Plan.is_active.is_(True))
    return query.order_by(Plan.id.desc()).all()


@router.post("", response_model=PlanResponse, status_code=status.HTTP_201_CREATED)
def create_plan(payload: PlanCreate, db: Session = Depends(get_db)):
    plan = Plan(**payload.model_dump())
    db.add(plan)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="رمز الباقة مستخدم من قبل")
    db.refresh(plan)
    return plan


@router.patch("/{plan_id}", response_model=PlanResponse)
def update_plan(plan_id: int, payload: PlanUpdate, db: Session = Depends(get_db)):
    plan = db.get(Plan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="الباقة غير موجودة")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(plan, field, value)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="رمز الباقة مستخدم من قبل")
    db.refresh(plan)
    return plan
