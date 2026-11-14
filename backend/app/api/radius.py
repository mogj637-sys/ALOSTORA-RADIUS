import os
import secrets
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.core import Router
from app.schemas.radius import (
    RadiusAccountingRequest,
    RadiusAccountingResponse,
    RadiusAuthorizeRequest,
)
from app.services.credentials import CredentialEncryptionNotConfigured
from app.services.router_secrets import RouterSecretEncryptionNotConfigured, decrypt_router_secret
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


@router.get(
    "/clients",
    dependencies=[Depends(require_radius_internal_key)],
)
def radius_clients(response: Response, db: Session = Depends(get_db)):
    # This endpoint is consumed only by the private FreeRADIUS container.
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
    response.headers["Pragma"] = "no-cache"
    configured = (
        db.query(Router)
        .filter(
            Router.radius_client_address.is_not(None),
        )
        .order_by(Router.id.asc())
        .all()
    )
    clients = []
    try:
        for item in configured:
            clients.append({
                "nas_identifier": item.nas_identifier,
                "ipaddr": item.radius_client_address,
                "shortname": item.nas_identifier,
                "secret": decrypt_router_secret(item.radius_secret_encrypted),
            })
    except (RouterSecretEncryptionNotConfigured, ValueError) as exc:
        raise HTTPException(status_code=503, detail="تعذر فك تشفير أحد أسرار RADIUS") from exc
    return {"clients": clients}




def _attribute(payload: dict[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if name not in payload:
            continue
        value = payload[name]
        if isinstance(value, dict) and "value" in value:
            value = value["value"]
        if isinstance(value, list):
            value = value[0] if value else default
        return default if value is None else value
    return default


def _accounting_status(value: Any) -> str:
    numeric = {1: "Start", 2: "Stop", 3: "Interim-Update"}
    if isinstance(value, str) and value.isdigit():
        value = int(value)
    if isinstance(value, int):
        value = numeric.get(value, value)
    aliases = {
        "start": "Start",
        "stop": "Stop",
        "interim-update": "Interim-Update",
        "interim_update": "Interim-Update",
    }
    return aliases.get(str(value).lower(), str(value))


def _event_timestamp(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)) or (isinstance(value, str) and value.isdigit()):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value


def _hex_attribute(payload: dict[str, Any], *names: str) -> str | None:
    value = _attribute(payload, *names)
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.hex()
    text = str(value).strip()
    if text.startswith("0x"):
        text = text[2:]
    if len(text) % 2 == 0 and all(char in "0123456789abcdefABCDEF" for char in text):
        return text.lower()
    return text.encode("utf-8").hex()


def _normalize_authorize(payload: dict[str, Any]) -> RadiusAuthorizeRequest:
    return RadiusAuthorizeRequest(
        nas_identifier=_attribute(payload, "nas_identifier", "NAS-Identifier"),
        username=_attribute(payload, "username", "User-Name"),
        password=_attribute(payload, "password", "User-Password", default=""),
        chap_password_hex=_hex_attribute(payload, "chap_password_hex", "CHAP-Password-Hex", "CHAP-Password"),
        chap_challenge_hex=_hex_attribute(payload, "chap_challenge_hex", "CHAP-Challenge-Hex", "CHAP-Challenge"),
        framed_ip_address=_attribute(payload, "framed_ip_address", "Framed-IP-Address"),
        calling_station_id=_attribute(payload, "calling_station_id", "Calling-Station-Id"),
    )


def _normalize_accounting(payload: dict[str, Any]) -> RadiusAccountingRequest:
    return RadiusAccountingRequest(
        nas_identifier=_attribute(payload, "nas_identifier", "NAS-Identifier"),
        username=_attribute(payload, "username", "User-Name"),
        acct_session_id=_attribute(payload, "acct_session_id", "Acct-Session-Id"),
        status_type=_accounting_status(_attribute(payload, "status_type", "Acct-Status-Type")),
        event_timestamp=_event_timestamp(_attribute(payload, "event_timestamp", "Event-Timestamp")),
        framed_ip_address=_attribute(payload, "framed_ip_address", "Framed-IP-Address"),
        calling_station_id=_attribute(payload, "calling_station_id", "Calling-Station-Id"),
        session_time_seconds=int(_attribute(payload, "session_time_seconds", "Acct-Session-Time", default=0)),
        input_octets=int(_attribute(payload, "input_octets", "Acct-Input-Octets", default=0)),
        output_octets=int(_attribute(payload, "output_octets", "Acct-Output-Octets", default=0)),
        input_gigawords=int(_attribute(payload, "input_gigawords", "Acct-Input-Gigawords", default=0)),
        output_gigawords=int(_attribute(payload, "output_gigawords", "Acct-Output-Gigawords", default=0)),
    )

@router.post(
    "/authorize",
    response_model=dict[str, str | int],
    dependencies=[Depends(require_radius_internal_key)],
)
def radius_authorize(payload: dict[str, Any] = Body(...), db: Session = Depends(get_db)):
    request = _normalize_authorize(payload)
    try:
        result = authorize_card(
            db,
            nas_identifier=request.nas_identifier,
            username=request.username,
            password=request.password,
            chap_password_hex=request.chap_password_hex,
            chap_challenge_hex=request.chap_challenge_hex,
            framed_ip_address=request.framed_ip_address,
            calling_station_id=request.calling_station_id,
        )
    except CredentialEncryptionNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    if not result["accepted"]:
        return JSONResponse(status_code=401, content={"reply:Reply-Message": result["reason"]})
    # rlm_rest maps these prefixed keys directly into the RADIUS reply list.
    return JSONResponse(
        status_code=200,
        content={
            "control:Auth-Type": "Accept",
            **{f"reply:{key}": value for key, value in result["reply"].items()},
        },
    )


@router.post(
    "/accounting",
    response_model=RadiusAccountingResponse,
    dependencies=[Depends(require_radius_internal_key)],
)
def radius_accounting(payload: dict[str, Any] = Body(...), db: Session = Depends(get_db)):
    request = _normalize_accounting(payload)
    result = process_accounting(db, request.model_dump())
    if not result.get("processed", False):
        return JSONResponse(status_code=409, content=result)
    return result
