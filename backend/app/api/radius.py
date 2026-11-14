import os
import secrets

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.radius import (
    RadiusAccountingRequest,
    RadiusAccountingResponse,
    RadiusAuthorizeRequest,
    RadiusAuthorizeResponse,
)
from app.services.credentials import CredentialEncryptionNotConfigured
from app.services.radius_service import authorize_card, process_accounting

router = APIRouter(prefix="/internal/radius", tags=["radius-internal"])


def require_radius_internal_key(
    x_radius_internal_key: str | None = Header(default=None, alias="X-Radius-Internal-Key"),
) -> None:
    expected = os.getenv("RADIUS_INTERNAL_API_KEY")
    if not expected or len(expected) < 32:
        raise HTTPException(status_code=503, detail="RADIUS_INTERNAL_API_KEY is not configured securely")
    if not x_radius_internal_key or not secrets.compare_digest(expected, x_radius_internal_key):
        raise HTTPException(status_code=401, detail="Unauthorized RADIUS internal request")


@router.post(
    "/authorize",
    response_model=RadiusAuthorizeResponse,
    dependencies=[Depends(require_radius_internal_key)],
)
def radius_authorize(payload: RadiusAuthorizeRequest, db: Session = Depends(get_db)):
    try:
        result = authorize_card(
            db,
            nas_identifier=payload.nas_identifier,
            username=payload.username,
            password=payload.password,
            framed_ip_address=payload.framed_ip_address,
            calling_station_id=payload.calling_station_id,
        )
    except CredentialEncryptionNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    if not result["accepted"]:
        return JSONResponse(status_code=401, content=result)
    return result


@router.post(
    "/accounting",
    response_model=RadiusAccountingResponse,
    dependencies=[Depends(require_radius_internal_key)],
)
def radius_accounting(payload: RadiusAccountingRequest, db: Session = Depends(get_db)):
    result = process_accounting(db, payload.model_dump())
    if not result["processed"]:
        return JSONResponse(status_code=409, content=result)
    return result
