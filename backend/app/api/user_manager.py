from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_owner
from app.db.session import get_db
from app.models.core import Card, Router
from app.models.user_manager import UserManagerCardSource, UserManagerSyncRun
from app.models.user_manager_preview import UserManagerImportPreview
from app.services.user_manager_preview import build_user_manager_preview
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



@router.post("/{router_id}/user-manager/preview-user")
def preview_user_manager_user_endpoint(
    router_id: int,
    payload: UserManagerUserInspectRequest,
    db: Session = Depends(get_db),
):
    """Persist a safe, single-user preview; this endpoint never imports or mutates a card."""
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
        source_user = inspect_user_manager_user(
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

    if source_user is None:
        raise HTTPException(status_code=404, detail="الكرت غير موجود في User Manager")

    # The diagnostic adapter does not read credentials. Missing password data is
    # therefore explicitly marked unavailable, never guessed as username-only.
    source_record = dict(source_user)
    if not source_record.get("external_id"):
        raise HTTPException(
            status_code=422,
            detail="معرّف المستخدم الأصلي غير متاح؛ لم يتم حفظ المعاينة لتجنب إنشاء هوية مصدر وهمية",
        )
    source_record["username"] = source_user.get("username") or payload.username
    existing_card = (
        db.query(Card.id)
        .filter(Card.username == source_record["username"])
        .first()
    )
    existing_cards = (
        {source_record["username"]: str(existing_card[0])}
        if existing_card is not None else {}
    )
    source_link = (
        db.query(UserManagerCardSource.card_id)
        .filter(
            UserManagerCardSource.router_id == router_id,
            UserManagerCardSource.external_user_id == str(source_record.get("external_id") or ""),
        )
        .first()
    )
    # A source mapping remains meaningful even if its card_id is temporarily
    # null (for example, an interrupted/legacy migration). Preserve that fact
    # so the preview cannot misclassify the source record as a brand-new card.
    links = (
        {
            str(source_record["external_id"]):
                str(source_link[0]) if source_link[0] is not None else None
        }
        if source_link is not None else {}
    )
    classified = build_user_manager_preview(
        [source_record],
        existing_cards_by_username=existing_cards,
        source_links_by_external_id=links,
    )[0]

    run = UserManagerSyncRun(
        id=uuid4(),
        router_id=router_id,
        run_type="preview",
        status="completed",
        discovered_users=1,
        checkpoint={"mode": "single_user_preview", "username": source_record["username"]},
        source_summary={"previewed_users": 1, "credentials_read": False},
        error_summary=[],
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
    )
    preview = UserManagerImportPreview(
        sync_run_id=run.id,
        external_user_id=classified["external_user_id"],
        username=classified["username"] or payload.username,
        source_profile_id=classified["source_profile_id"],
        classification=classified["classification"],
        credential_mode=classified["credential_mode"],
        credential_state=classified["credential_state"],
        matched_card_id=(
            source_link[0] if source_link is not None and source_link[0] is not None
            else existing_card[0] if existing_card is not None else None
        ),
        safe_snapshot=classified["safe_snapshot"],
        issues=classified["issues"],
        source_fingerprint=classified["source_fingerprint"],
    )
    try:
        db.add(run)
        db.add(preview)
        db.commit()
        db.refresh(preview)
    except Exception:
        db.rollback()
        raise

    return {
        "sync_run_id": str(run.id),
        "preview_id": preview.id,
        "username": preview.username,
        "classification": preview.classification,
        "credential_mode": preview.credential_mode,
        "credential_state": preview.credential_state,
        "issues": preview.issues,
        "safe_snapshot": preview.safe_snapshot,
        "source_fingerprint": preview.source_fingerprint,
        "read_only": True,
        "imported": False,
        "credentials_read": False,
    }



@router.get("/{router_id}/user-manager/previews")
def list_user_manager_previews(
    router_id: int,
    run_id: UUID | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """List safe, persisted preview rows for one router; never reads RouterOS."""
    item = db.get(Router, router_id)
    if item is None:
        raise HTTPException(status_code=404, detail="الراوتر غير موجود")

    runs_query = db.query(UserManagerSyncRun).filter(
        UserManagerSyncRun.router_id == router_id,
        UserManagerSyncRun.run_type == "preview",
    )
    if run_id is not None:
        run = runs_query.filter(UserManagerSyncRun.id == run_id).first()
        if run is None:
            raise HTTPException(status_code=404, detail="عملية المعاينة غير موجودة لهذا الراوتر")
    else:
        run = runs_query.order_by(
            UserManagerSyncRun.created_at.desc(),
            UserManagerSyncRun.id.desc(),
        ).first()

    if run is None:
        return {"run": None, "items": [], "total": 0, "offset": offset, "limit": limit}

    previews_query = db.query(UserManagerImportPreview).filter(
        UserManagerImportPreview.sync_run_id == run.id
    )
    total = previews_query.count()
    rows = (
        previews_query
        .order_by(UserManagerImportPreview.id.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {
        "run": {
            "id": str(run.id),
            "status": run.status,
            "discovered_users": run.discovered_users,
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        },
        "items": [
            {
                "id": row.id,
                "external_user_id": row.external_user_id,
                "username": row.username,
                "source_profile_id": row.source_profile_id,
                "classification": row.classification,
                "credential_mode": row.credential_mode,
                "credential_state": row.credential_state,
                "matched_card_id": str(row.matched_card_id) if row.matched_card_id else None,
                "safe_snapshot": row.safe_snapshot,
                "issues": row.issues,
            }
            for row in rows
        ],
        "total": total,
        "offset": offset,
        "limit": limit,
        "read_only": True,
        "imported": False,
        "credentials_read": False,
    }
