from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_owner
from app.db.session import get_db
from app.models.auth import AdminUser, Role, Permission
from app.schemas.admins import AdminRoleResponse, AdminUserCreate, AdminUserResponse, AdminUserUpdate
from app.security import hash_password

router = APIRouter(prefix="/api/v1/admins", tags=["administrators"])


def _user_response(user: AdminUser) -> AdminUserResponse:
    return AdminUserResponse(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        is_active=user.is_active,
        roles=sorted(role.code for role in user.roles),
        last_login_at=user.last_login_at,
        created_at=user.created_at,
    )


def _resolve_roles(db: Session, role_codes: list[str]) -> list[Role]:
    if "owner" in role_codes:
        raise HTTPException(status_code=422, detail="لا يمكن إنشاء أو منح صلاحية مدير النظام من شاشة الموظفين")
    roles = db.query(Role).filter(Role.code.in_(role_codes)).all()
    found = {role.code for role in roles}
    missing = sorted(set(role_codes) - found)
    if missing:
        raise HTTPException(status_code=422, detail=f"الأدوار غير معروفة: {', '.join(missing)}")
    return roles


@router.get("/roles", response_model=list[AdminRoleResponse])
def list_roles(
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_owner),
) -> list[AdminRoleResponse]:
    return [
        AdminRoleResponse(code=role.code, name=role.name, description=role.description)
        for role in db.query(Role).order_by(Role.id).all()
    ]


@router.get("", response_model=list[AdminUserResponse])
def list_admins(
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_owner),
) -> list[AdminUserResponse]:
    users = (
        db.query(AdminUser)
        .options(selectinload(AdminUser.roles))
        .order_by(AdminUser.id)
        .all()
    )
    return [_user_response(user) for user in users]


@router.post("", response_model=AdminUserResponse, status_code=status.HTTP_201_CREATED)
def create_admin(
    payload: AdminUserCreate,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_owner),
) -> AdminUserResponse:
    if db.query(AdminUser).filter(AdminUser.username == payload.username).first():
        raise HTTPException(status_code=409, detail="اسم المستخدم مستخدم بالفعل")
    roles = _resolve_roles(db, payload.role_codes)
    try:
        password_hash = hash_password(payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    user = AdminUser(
        username=payload.username,
        display_name=payload.display_name,
        password_hash=password_hash,
        is_active=True,
        roles=roles,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _user_response(user)


@router.patch("/{user_id}", response_model=AdminUserResponse)
def update_admin(
    user_id: int,
    payload: AdminUserUpdate,
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(get_current_owner),
) -> AdminUserResponse:
    user = (
        db.query(AdminUser)
        .options(selectinload(AdminUser.roles))
        .filter(AdminUser.id == user_id)
        .first()
    )
    if user is None:
        raise HTTPException(status_code=404, detail="حساب الإدارة غير موجود")

    next_roles = _resolve_roles(db, payload.role_codes) if payload.role_codes is not None else user.roles
    next_active = payload.is_active if payload.is_active is not None else user.is_active
    keeps_owner = any(role.code == "owner" for role in next_roles)

    if user.id == current_user.id and (not next_active or not keeps_owner):
        raise HTTPException(status_code=400, detail="لا يمكن تعطيل حسابك الحالي أو سحب صلاحية مدير النظام منه")

    if user.is_active and any(role.code == "owner" for role in user.roles) and (not next_active or not keeps_owner):
        active_owners = (
            db.query(AdminUser)
            .join(AdminUser.roles)
            .filter(AdminUser.is_active.is_(True), Role.code == "owner")
            .count()
        )
        if active_owners <= 1:
            raise HTTPException(status_code=400, detail="لا يمكن تعطيل أو تخفيض صلاحية آخر مدير نظام")

    if payload.display_name is not None:
        user.display_name = payload.display_name
    if payload.password:
        try:
            user.password_hash = hash_password(payload.password)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    if payload.role_codes is not None:
        user.roles = next_roles
    user.is_active = next_active
    db.commit()
    db.refresh(user)
    return _user_response(user)



@router.get("/permissions")
def list_permissions(
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_owner),
):
    return [
        {"code": item.code, "name": item.name, "module": item.module, "description": item.description}
        for item in db.query(Permission).order_by(Permission.module, Permission.id).all()
    ]


@router.get("/roles/{role_code}/permissions")
def get_role_permissions(
    role_code: str,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_owner),
):
    role = db.query(Role).filter(Role.code == role_code).first()
    if role is None:
        raise HTTPException(status_code=404, detail="الدور الإداري غير موجود")
    return {"role_code": role.code, "permission_codes": sorted(item.code for item in role.permissions)}


@router.put("/roles/{role_code}/permissions")
def update_role_permissions(
    role_code: str,
    permission_codes: list[str] = Body(..., embed=True),
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_owner),
):
    role = db.query(Role).filter(Role.code == role_code).first()
    if role is None:
        raise HTTPException(status_code=404, detail="الدور الإداري غير موجود")
    if role.code == "owner":
        raise HTTPException(status_code=400, detail="صلاحيات مدير النظام ثابتة ولا يمكن تقليصها")
    normalized = list(dict.fromkeys(code.strip() for code in permission_codes if code.strip()))
    permissions = db.query(Permission).filter(Permission.code.in_(normalized)).all() if normalized else []
    found = {item.code for item in permissions}
    missing = sorted(set(normalized) - found)
    if missing:
        raise HTTPException(status_code=422, detail=f"صلاحيات غير معروفة: {', '.join(missing)}")
    role.permissions = permissions
    db.commit()
    return {"role_code": role.code, "permission_codes": sorted(item.code for item in permissions)}
