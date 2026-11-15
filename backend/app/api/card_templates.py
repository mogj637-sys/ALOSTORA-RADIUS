from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_owner
from app.db.session import get_db
from app.models.core import CardTemplate
from app.schemas.card_templates import CardTemplateCreate, CardTemplateUpdate, CardTemplateResponse

router = APIRouter(prefix="/api/v1/card-templates", tags=["card-templates"], dependencies=[Depends(get_current_owner)])

@router.get("", response_model=list[CardTemplateResponse])
def list_templates(db: Session = Depends(get_db)):
    return db.query(CardTemplate).order_by(CardTemplate.is_default.desc(), CardTemplate.id.asc()).all()

@router.post("", response_model=CardTemplateResponse, status_code=status.HTTP_201_CREATED)
def create_template(payload: CardTemplateCreate, db: Session = Depends(get_db)):
    item = CardTemplate(**payload.model_dump())
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="رمز القالب مستخدم من قبل")
    db.refresh(item)
    return item

@router.patch("/{template_id}", response_model=CardTemplateResponse)
def update_template(template_id: int, payload: CardTemplateUpdate, db: Session = Depends(get_db)):
    item = db.get(CardTemplate, template_id)
    if item is None:
        raise HTTPException(status_code=404, detail="القالب غير موجود")
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail="لا توجد تغييرات لحفظها")
    if changes.get("is_default"):
        db.query(CardTemplate).filter(CardTemplate.id != item.id).update({CardTemplate.is_default: False})
    for key, value in changes.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item

@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template(template_id: int, db: Session = Depends(get_db)):
    item = db.get(CardTemplate, template_id)
    if item is None:
        raise HTTPException(status_code=404, detail="القالب غير موجود")
    if item.is_default:
        raise HTTPException(status_code=409, detail="لا يمكن حذف القالب الافتراضي")
    db.delete(item)
    db.commit()
