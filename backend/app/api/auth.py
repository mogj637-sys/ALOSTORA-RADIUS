import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.auth import AdminUser
from app.schemas.auth import CurrentUserResponse, LoginRequest, TokenResponse
from app.security import create_access_token, verify_password
from app.services.audit import record_audit

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(AdminUser).filter(AdminUser.username == payload.username).first()
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="اسم المستخدم أو كلمة المرور غير صحيحة",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user.last_login_at = datetime.now(timezone.utc)
    record_audit(db, user, "auth.login", "admin_user", f"تسجيل دخول ناجح للحساب {user.username}", entity_id=user.id, request=request)
    db.commit()

    expires_in = int(os.getenv("JWT_ACCESS_TOKEN_MINUTES", "30")) * 60
    try:
        token = create_access_token(str(user.id))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="مفتاح الأمان APP_SECRET_KEY غير مضبوط") from exc
    return TokenResponse(access_token=token, expires_in=expires_in)


@router.get("/me", response_model=CurrentUserResponse)
def current_identity(user: AdminUser = Depends(get_current_user)) -> CurrentUserResponse:
    return CurrentUserResponse(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        roles=[role.code for role in user.roles],
        point_of_sale_ids=sorted(point.id for point in user.point_of_sales),
        permissions=(
            ["*"] if any(role.code == "owner" for role in user.roles)
            else sorted({permission.code for role in user.roles for permission in role.permissions})
        ),
    )
