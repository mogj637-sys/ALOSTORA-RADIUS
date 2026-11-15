from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_owner
from app.db.session import get_db
from app.models.core import Router
from app.services.router_secrets import (
    RouterSecretEncryptionNotConfigured,
    decrypt_router_secret,
)
from app.services.user_manager_routeros import (
    UserManagerConnectionError,
    inspect_routeros_user_manager,
    inspect_user_manager_user,
)

router = APIRouter(
    prefix="/api/v1/routers",
    tags=["user-manager-sync"],
    dependencies=[Depends(get_current_owner)],
)


@router.post("/{router_id}/user-manager/test-connection")
def test_user_manager_connection(router_id: int, db: Session = Depends(get_db)):
    item = db.get(Router, router_id)
    if item is None:
        raise HTTPException(status_code=404, detail="الراوتر غير موجود")
    if not item.is_active:
        raise HTTPException(status_code=409, detail="الراوتر غير نشط")
    if not item.api_username or not item.api_secret_encrypted:
        raise HTTPException(
            status_code=409,
            detail="بيانات RouterOS API غير محفوظة لهذا الراوتر",
        )
    try:
        api_password = decrypt_router_secret(item.api_secret_encrypted)
        probe = inspect_routeros_user_manager(
            host=item.management_host,
            port=item.api_port,
            username=item.api_username,
            password=api_password,
        )
    except RouterSecretEncryptionNotConfigured as exc:
        raise HTTPException(status_code=503, detail="مفتاح تشفير أسرار الراوتر غير مضبوط") from exc
    except ValueError as exc:
        raise HTTPException(status_code=503, detail="تعذر فك تشفير بيانات API المحفوظة") from exc
    except UserManagerConnectionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {
        "connected": True,
        "router_id": item.id,
        "router_name": item.name,
        "identity": probe.identity,
        "routeros_version": probe.version,
        "board_name": probe.board_name,
        "architecture_name": probe.architecture_name,
        "uptime": probe.uptime,
        "user_manager_available": probe.user_manager_available,
        "resources": probe.resources,
        "warnings": probe.warnings,
        "read_only": True,
    }



class UserManagerUserInspectRequest(BaseModel):
    username: str = Field(min_length=1, max_length=120)


@router.post("/{router_id}/user-manager/inspect-user")
def inspect_user_manager_user_endpoint(
    router_id: int,
    payload: UserManagerUserInspectRequest,
    db: Session = Depends(get_db),
):
    """Read one exact username for diagnostics; never imports or changes it."""
    item = db.get(Router, router_id)
    if item is None:
        raise HTTPException(status_code=404, detail="الراوتر غير موجود")
    if not item.is_active:
        raise HTTPException(status_code=409, detail="الراوتر غير نشط")
    if not item.api_username or not item.api_secret_encrypted:
        raise HTTPException(
            status_code=409,
            detail="بيانات RouterOS API غير محفوظة لهذا الراوتر",
        )
    try:
        api_password = decrypt_router_secret(item.api_secret_encrypted)
        user = inspect_user_manager_user(
            host=item.management_host,
            port=item.api_port,
            username=item.api_username,
            password=api_password,
            target_username=payload.username,
        )
    except RouterSecretEncryptionNotConfigured as exc:
        raise HTTPException(status_code=503, detail="مفتاح تشفير أسرار الراوتر غير مضبوط") from exc
    except ValueError as exc:
        raise HTTPException(status_code=503, detail="تعذر فك تشفير بيانات API المحفوظة") from exc
    except UserManagerConnectionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {
        "router_id": item.id,
        "found": user is not None,
        "user": user,
        "read_only": True,
        "credentials_read": False,
        "imported": False,
    }
