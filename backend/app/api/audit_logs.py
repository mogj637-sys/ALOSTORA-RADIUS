from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.audit import AuditLog
from app.models.auth import AdminUser

router = APIRouter(prefix="/api/v1/audit-logs", tags=["audit"])


@router.get("", dependencies=[Depends(require_permission("audit.view"))])
def list_audit_logs(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    action: str | None = Query(default=None, max_length=80),
    entity_type: str | None = Query(default=None, max_length=80),
    db: Session = Depends(get_db),
    _: AdminUser = Depends(require_permission("audit.view")),
):
    query = db.query(AuditLog)
    if action:
        query = query.filter(AuditLog.action == action)
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)
    total = query.count()
    rows = query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).offset(offset).limit(limit).all()
    return {
        "total": total,
        "items": [
            {
                "id": row.id,
                "actor_id": row.actor_id,
                "actor_username": row.actor_username,
                "action": row.action,
                "entity_type": row.entity_type,
                "entity_id": row.entity_id,
                "summary": row.summary,
                "details": row.details,
                "ip_address": row.ip_address,
                "created_at": row.created_at,
            }
            for row in rows
        ],
    }
