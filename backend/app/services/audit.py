from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.auth import AdminUser


def record_audit(
    db: Session,
    actor: AdminUser,
    action: str,
    entity_type: str,
    summary: str,
    *,
    entity_id: str | int | None = None,
    details: dict[str, Any] | None = None,
    request: Request | None = None,
) -> None:
    client_host = request.client.host if request and request.client else None
    user_agent = request.headers.get("user-agent") if request else None
    db.add(
        AuditLog(
            actor_id=actor.id,
            actor_username=actor.username,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            summary=summary[:300],
            details=details or {},
            ip_address=client_host,
            user_agent=user_agent[:300] if user_agent else None,
        )
    )
