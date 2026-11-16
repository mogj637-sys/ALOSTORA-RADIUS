from fastapi import APIRouter, Depends, HTTPException, status
from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.auth import AdminUser
from app.models.core import Router
from app.services.audit import record_audit
from app.schemas.routers import RouterCreate, RouterResponse, RouterUpdate
from app.services.router_secrets import (
    RouterSecretEncryptionNotConfigured,
    encrypt_router_secret,
)
from app.services.router_secrets import decrypt_router_secret
from app.services.routeros_probe import RouterConnectionError, probe_routeros_system

router = APIRouter(
    prefix="/api/v1/routers",
    tags=["routers"],
)


def _encrypt(value: str) -> str:
    try:
        return encrypt_router_secret(value)
    except RouterSecretEncryptionNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("", response_model=list[RouterResponse], dependencies=[Depends(require_permission("routers.view"))])
def list_routers(include_inactive: bool = False, db: Session = Depends(get_db)):
    query = db.query(Router)
    if not include_inactive:
        query = query.filter(Router.is_active.is_(True))
    return query.order_by(Router.id.desc()).all()


@router.post("/{router_id}/test-connection", dependencies=[Depends(require_permission("routers.view"))])
def test_router_connection(router_id: int, db: Session = Depends(get_db)):
    """Read basic RouterOS metadata only; never changes router configuration."""
    item = db.get(Router, router_id)
    if item is None:
        raise HTTPException(status_code=404, detail="الراوتر غير موجود")
    if not item.is_active:
        raise HTTPException(status_code=409, detail="الراوتر غير نشط")
    if not item.api_username or not item.api_secret_encrypted:
        raise HTTPException(status_code=409, detail="بيانات RouterOS API غير محفوظة لهذا الراوتر")
    try:
        password = decrypt_router_secret(item.api_secret_encrypted)
        result = probe_routeros_system(
            host=item.management_host,
            port=item.api_port,
            username=item.api_username,
            password=password,
        )
    except RouterSecretEncryptionNotConfigured as exc:
        raise HTTPException(status_code=503, detail="مفتاح تشفير أسرار الراوتر غير مضبوط") from exc
    except ValueError as exc:
        raise HTTPException(status_code=503, detail="تعذر فك تشفير بيانات API المحفوظة") from exc
    except RouterConnectionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    item.last_seen_at = datetime.now(timezone.utc)
    if result.get("version"):
        item.routeros_version = result["version"][:30]
    db.commit()
    db.refresh(item)
    return {"router_id": item.id, "router_name": item.name, "last_seen_at": item.last_seen_at, **result, "read_only": True}


@router.post("", response_model=RouterResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission("routers.create"))])
def create_router(payload: RouterCreate, db: Session = Depends(get_db), user: AdminUser = Depends(require_permission("routers.create"))):
    values = payload.model_dump(exclude={"api_secret", "radius_secret"})
    values["radius_secret_encrypted"] = _encrypt(payload.radius_secret)
    values["api_secret_encrypted"] = _encrypt(payload.api_secret) if payload.api_secret else None
    item = Router(**values)
    db.add(item)
    try:
        db.flush()
        record_audit(db, user, "router.created", "router", f"إضافة راوتر {item.name}", entity_id=item.id, details={"nas_identifier": item.nas_identifier, "management_host": item.management_host})
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="معرّف NAS مستخدم في راوتر آخر")
    db.refresh(item)
    return item


@router.patch("/{router_id}", response_model=RouterResponse, dependencies=[Depends(require_permission("routers.update"))])
def update_router(router_id: int, payload: RouterUpdate, db: Session = Depends(get_db), user: AdminUser = Depends(require_permission("routers.update"))):
    item = db.get(Router, router_id)
    if item is None:
        raise HTTPException(status_code=404, detail="الراوتر غير موجود")

    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail="يجب إرسال حقل واحد على الأقل")
    safe_changes = {key: value for key, value in changes.items() if key not in {"radius_secret", "api_secret"}}
    if "radius_secret" in changes:
        changes["radius_secret_encrypted"] = _encrypt(changes.pop("radius_secret"))
    if "api_secret" in changes:
        value = changes.pop("api_secret")
        changes["api_secret_encrypted"] = _encrypt(value) if value is not None else None
    for field, value in changes.items():
        setattr(item, field, value)
    record_audit(db, user, "router.updated", "router", f"تعديل راوتر {item.name}", entity_id=item.id, details={"changed_fields": list(safe_changes.keys()), "secrets_changed": ("radius_secret" in payload.model_fields_set or "api_secret" in payload.model_fields_set)})
    db.commit()
    db.refresh(item)
    return item
