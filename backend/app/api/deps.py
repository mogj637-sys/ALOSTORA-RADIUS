import os

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.auth import AdminUser, Role
from app.services.permissions import has_permission

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> AdminUser:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    secret = os.getenv("APP_SECRET_KEY", "development-only-change-me")
    try:
        payload = jwt.decode(credentials.credentials, secret, algorithms=["HS256"])
        subject = payload.get("sub")
        user_id = int(subject)
    except (InvalidTokenError, TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.get(AdminUser, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Account is unavailable")
    return user


def get_current_owner(
    user: AdminUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminUser:
    owner_role_id = db.query(Role.id).filter(Role.code == "owner").scalar()
    if owner_role_id is None:
        raise HTTPException(status_code=403, detail="هذه العملية تتطلب صلاحية مدير النظام")
    current_owner = (
        db.query(AdminUser.id)
        .join(AdminUser.roles)
        .filter(
            AdminUser.id == user.id,
            AdminUser.is_active.is_(True),
            Role.id == owner_role_id,
        )
        .first()
    )
    if current_owner is None:
        raise HTTPException(status_code=403, detail="هذه العملية تتطلب صلاحية مدير النظام")
    return user



def require_permission(permission_code: str):
    def permission_dependency(
        user: AdminUser = Depends(get_current_user),
    ) -> AdminUser:
        if not has_permission(user, permission_code):
            raise HTTPException(
                status_code=403,
                detail=f"ليست لديك صلاحية تنفيذ هذه العملية ({permission_code})",
            )
        return user

    return permission_dependency
