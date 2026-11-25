from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_permission
from app.db.session import get_db
from app.models.auth import AdminUser
from app.models.core import CardBatch, CardTemplate, Plan, PrintJob
from app.services.audit import record_audit
from app.services.permissions import has_permission
from app.schemas.card_templates import CardTemplateCreate, CardTemplateUpdate, CardTemplateResponse

router = APIRouter(prefix="/api/v1/card-templates", tags=["card-templates"])


@router.get("/printing-options", response_model=list[CardTemplateResponse])
def list_printing_template_options(
    db: Session = Depends(get_db),
    user: AdminUser = Depends(get_current_user),
):
    if not has_permission(user, "printing.create") or not has_permission(user, "printing.credentials"):
        raise HTTPException(status_code=403, detail="تتطلب خيارات قوالب الطباعة صلاحية الطباعة وبيانات الدخول")
    return db.query(CardTemplate).order_by(CardTemplate.is_default.desc(), CardTemplate.id.asc()).all()


@router.get("", response_model=list[CardTemplateResponse], dependencies=[Depends(require_permission("templates.view"))])
def list_templates(db: Session = Depends(get_db)):
    return db.query(CardTemplate).order_by(CardTemplate.is_default.desc(), CardTemplate.id.asc()).all()

@router.post("", response_model=CardTemplateResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission("templates.create"))])
def create_template(payload: CardTemplateCreate, db: Session = Depends(get_db), user: AdminUser = Depends(require_permission("templates.create"))):
    plan = db.get(Plan, payload.plan_id)
    if plan is None or not plan.is_active:
        raise HTTPException(status_code=422, detail="اختر باقة موجودة ومفعلة لربطها بالقالب")
    item = CardTemplate(**payload.model_dump())
    db.add(item)
    try:
        db.flush()
        record_audit(db, user, "card_template.created", "card_template", f"إنشاء قالب {item.name}", entity_id=item.id, details={"code": item.code, "plan_id": item.plan_id})
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="رمز القالب مستخدم من قبل")
    db.refresh(item)
    return item

@router.patch("/{template_id}", response_model=CardTemplateResponse, dependencies=[Depends(require_permission("templates.update"))])
def update_template(template_id: int, payload: CardTemplateUpdate, db: Session = Depends(get_db), user: AdminUser = Depends(require_permission("templates.update"))):
    item = db.get(CardTemplate, template_id)
    if item is None:
        raise HTTPException(status_code=404, detail="القالب غير موجود")
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail="لا توجد تغييرات لحفظها")
    if "plan_id" in changes and changes["plan_id"] is not None:
        plan = db.get(Plan, changes["plan_id"])
        if plan is None or not plan.is_active:
            raise HTTPException(status_code=422, detail="اختر باقة موجودة ومفعلة لربطها بالقالب")
    before = {
        key: str(getattr(item, key)) if isinstance(getattr(item, key), Decimal) else getattr(item, key)
        for key in changes
    }
    audit_changes = {
        key: str(value) if isinstance(value, Decimal) else value
        for key, value in changes.items()
    }
    if changes.get("is_default"):
        db.query(CardTemplate).filter(CardTemplate.id != item.id).update({CardTemplate.is_default: False})
    for key, value in changes.items():
        setattr(item, key, value)
    record_audit(
        db,
        user,
        "card_template.updated",
        "card_template",
        f"تعديل قالب {item.name}",
        entity_id=item.id,
        details={"before": before, "after": audit_changes},
    )
    db.commit()
    db.refresh(item)
    return item

@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_permission("templates.delete"))])
def delete_template(template_id: int, db: Session = Depends(get_db), user: AdminUser = Depends(require_permission("templates.delete"))):
    item = db.get(CardTemplate, template_id)
    if item is None:
        raise HTTPException(status_code=404, detail="القالب غير موجود")
    if item.is_default:
        raise HTTPException(status_code=409, detail="لا يمكن حذف القالب الافتراضي")
    if db.query(CardBatch.id).filter(CardBatch.template_code == item.code).first() or db.query(PrintJob.id).filter(PrintJob.template_code == item.code).first():
        raise HTTPException(status_code=409, detail="لا يمكن حذف قالب مرتبط بدفعات أو عمليات طباعة محفوظة")
    record_audit(db, user, "card_template.deleted", "card_template", f"حذف قالب {item.name}", entity_id=item.id, details={"code": item.code, "plan_id": item.plan_id})
    db.delete(item)
    db.commit()
