from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_owner
from app.db.session import get_db
from app.models.auth import AdminUser, Role, Permission, AdminUserPermissionOverride
from app.models.core import PointOfSale
from app.schemas.admins import AdminPermissionOverride, AdminRoleCreate, AdminRoleResponse, AdminUserCreate, AdminUserResponse, AdminUserUpdate
from app.security import hash_password
from app.services.audit import record_audit
from app.services.permissions import card_visibility

router = APIRouter(prefix="/api/v1/admins", tags=["administrators"])


def _user_response(user: AdminUser) -> AdminUserResponse:
    return AdminUserResponse(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        is_active=user.is_active,
        roles=sorted(role.code for role in user.roles),
        point_of_sale_ids=sorted(point.id for point in user.point_of_sales),
        card_visibility=card_visibility(user),
        permission_overrides=[
            AdminPermissionOverride(
                permission_code=item.permission.code,
                allowed=item.allowed,
            )
            for item in user.permission_overrides
        ],
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


def _resolve_permission_overrides(
    db: Session,
    entries: list[AdminPermissionOverride],
) -> list[AdminUserPermissionOverride]:
    codes = [item.permission_code.strip() for item in entries]
    if len(codes) != len(set(codes)):
        raise HTTPException(status_code=422, detail="لا يمكن تكرار الصلاحية في تخصيص الموظف")
    permissions = db.query(Permission).filter(Permission.code.in_(codes)).all() if codes else []
    by_code = {item.code: item for item in permissions}
    missing = sorted(set(codes) - set(by_code))
    if missing:
        raise HTTPException(status_code=422, detail=f"صلاحيات غير معروفة: {', '.join(missing)}")
    return [
        AdminUserPermissionOverride(permission=by_code[item.permission_code.strip()], allowed=item.allowed)
        for item in entries
    ]


def _resolve_points_of_sale(db: Session, point_ids: list[int]) -> list[PointOfSale]:
    normalized = list(dict.fromkeys(point_ids))
    points = db.query(PointOfSale).filter(PointOfSale.id.in_(normalized)).all() if normalized else []
    if len(points) != len(normalized):
        raise HTTPException(status_code=422, detail="تتضمن قائمة نقاط البيع اختياراً غير صحيح")
    return points


def _require_current_owner(
    db: Session,
    current_user: AdminUser,
    *,
    lock: bool = False,
) -> Role:
    # Mutating owner-only requests lock the shared owner role row. A fresh
    # membership query then rejects requests whose caller was demoted after
    # the authentication dependency loaded its ORM object.
    owner_query = db.query(Role).filter(Role.code == "owner")
    if lock:
        owner_query = owner_query.with_for_update()
    owner_role = owner_query.first()
    if owner_role is None:
        raise HTTPException(status_code=403, detail="تعذر التحقق من صلاحية مدير النظام")

    caller_still_owner = (
        db.query(AdminUser.id)
        .join(AdminUser.roles)
        .filter(
            AdminUser.id == current_user.id,
            AdminUser.is_active.is_(True),
            Role.id == owner_role.id,
        )
        .first()
    )
    if caller_still_owner is None:
        raise HTTPException(status_code=403, detail="لم تعد تملك صلاحية مدير النظام لتنفيذ هذه العملية")
    return owner_role


@router.get("/roles", response_model=list[AdminRoleResponse])
def list_roles(
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(get_current_owner),
) -> list[AdminRoleResponse]:
    _require_current_owner(db, current_user)
    return [
        AdminRoleResponse(code=role.code, name=role.name, description=role.description)
        for role in db.query(Role).order_by(Role.id).all()
    ]


@router.post("/roles", response_model=AdminRoleResponse, status_code=status.HTTP_201_CREATED)
def create_role(
    payload: AdminRoleCreate,
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(get_current_owner),
) -> AdminRoleResponse:
    _require_current_owner(db, current_user, lock=True)
    if payload.code == "owner":
        raise HTTPException(status_code=422, detail="رمز owner محجوز لمدير النظام")
    if db.query(Role).filter(Role.code == payload.code).first():
        raise HTTPException(status_code=409, detail="رمز الدور مستخدم بالفعل")
    role = Role(code=payload.code, name=payload.name, description=payload.description)
    db.add(role)
    db.flush()
    record_audit(
        db, current_user, "role.created", "role",
        f"إنشاء دور إداري: {role.name}", entity_id=role.id,
        details={"code": role.code, "description": role.description},
    )
    db.commit()
    db.refresh(role)
    return AdminRoleResponse(code=role.code, name=role.name, description=role.description)


@router.get("", response_model=list[AdminUserResponse])
def list_admins(
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(get_current_owner),
) -> list[AdminUserResponse]:
    _require_current_owner(db, current_user)
    users = (
        db.query(AdminUser)
        .options(
            selectinload(AdminUser.roles),
            selectinload(AdminUser.point_of_sales),
            selectinload(AdminUser.permission_overrides).selectinload(AdminUserPermissionOverride.permission),
        )
        .order_by(AdminUser.id)
        .all()
    )
    return [_user_response(user) for user in users]


@router.post("", response_model=AdminUserResponse, status_code=status.HTTP_201_CREATED)
def create_admin(
    payload: AdminUserCreate,
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(get_current_owner),
) -> AdminUserResponse:
    _require_current_owner(db, current_user, lock=True)
    if db.query(AdminUser).filter(AdminUser.username == payload.username).first():
        raise HTTPException(status_code=409, detail="اسم المستخدم مستخدم بالفعل")
    roles = _resolve_roles(db, payload.role_codes)
    points = _resolve_points_of_sale(db, payload.point_of_sale_ids)
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
        point_of_sales=points,
        card_visibility=payload.card_visibility,
        permission_overrides=_resolve_permission_overrides(db, payload.permission_overrides),
    )
    db.add(user)
    db.flush()
    record_audit(db, current_user, "admin.created", "admin_user", f"إنشاء حساب إداري: {user.username}", entity_id=user.id, details={"role_codes": [role.code for role in roles]})
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
    owner_role = _require_current_owner(db, current_user, lock=True)

    user = (
        db.query(AdminUser)
        .options(
            selectinload(AdminUser.roles),
            selectinload(AdminUser.point_of_sales),
            selectinload(AdminUser.permission_overrides).selectinload(AdminUserPermissionOverride.permission),
        )
        .filter(AdminUser.id == user_id)
        .with_for_update()
        .first()
    )
    if user is None:
        raise HTTPException(status_code=404, detail="حساب الإدارة غير موجود")
    if any(role.code == "owner" for role in user.roles) and (
        payload.permission_overrides is not None or payload.card_visibility is not None
    ):
        raise HTTPException(status_code=400, detail="صلاحيات ونطاق مدير النظام ثابتة ولا تُدار من شاشة الموظفين")

    next_roles = _resolve_roles(db, payload.role_codes) if payload.role_codes is not None else user.roles
    next_active = payload.is_active if payload.is_active is not None else user.is_active
    next_points = _resolve_points_of_sale(db, payload.point_of_sale_ids) if payload.point_of_sale_ids is not None else user.point_of_sales
    next_visibility = payload.card_visibility if payload.card_visibility is not None else user.card_visibility
    keeps_owner = any(role.code == "owner" for role in next_roles)

    if user.id == current_user.id and (not next_active or not keeps_owner):
        raise HTTPException(status_code=400, detail="لا يمكن تعطيل حسابك الحالي أو سحب صلاحية مدير النظام منه")

    if user.is_active and any(role.code == "owner" for role in user.roles) and (not next_active or not keeps_owner):
        # The owner-role row is already locked for this transaction. This
        # serializes owner reductions and keeps the final active owner protected.
        active_owner_count = (
            db.query(AdminUser.id)
            .join(AdminUser.roles)
            .filter(AdminUser.is_active.is_(True), Role.id == owner_role.id)
            .count()
        )
        if active_owner_count <= 1:
            raise HTTPException(status_code=400, detail="لا يمكن تعطيل أو تخفيض صلاحية آخر مدير نظام")

    before = {
        "display_name": user.display_name,
        "is_active": user.is_active,
        "role_codes": sorted(role.code for role in user.roles),
        "point_of_sale_ids": sorted(point.id for point in user.point_of_sales),
        "card_visibility": user.card_visibility,
        "permission_overrides": [
            {"permission_code": item.permission.code, "allowed": item.allowed}
            for item in user.permission_overrides
        ],
    }
    if payload.display_name is not None:
        user.display_name = payload.display_name
    if payload.password:
        try:
            user.password_hash = hash_password(payload.password)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    if payload.role_codes is not None:
        user.roles = next_roles
    if payload.point_of_sale_ids is not None:
        user.point_of_sales = next_points
    if payload.card_visibility is not None:
        user.card_visibility = next_visibility
    if payload.permission_overrides is not None:
        user.permission_overrides = _resolve_permission_overrides(db, payload.permission_overrides)
    user.is_active = next_active
    record_audit(db, current_user, "admin.updated", "admin_user", f"تحديث حساب إداري: {user.username}", entity_id=user.id, details={"before": before, "after": {"display_name": user.display_name, "is_active": user.is_active, "role_codes": sorted(role.code for role in user.roles), "point_of_sale_ids": sorted(point.id for point in user.point_of_sales), "card_visibility": user.card_visibility, "permission_overrides": [{"permission_code": item.permission.code, "allowed": item.allowed} for item in user.permission_overrides]}, "password_changed": bool(payload.password)})
    db.commit()
    db.refresh(user)
    return _user_response(user)



@router.get("/permissions")
def list_permissions(
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(get_current_owner),
):
    _require_current_owner(db, current_user)
    return [
        {"code": item.code, "name": item.name, "module": item.module, "description": item.description}
        for item in db.query(Permission).order_by(Permission.module, Permission.id).all()
    ]


@router.get("/roles/{role_code}/permissions")
def get_role_permissions(
    role_code: str,
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(get_current_owner),
):
    _require_current_owner(db, current_user)
    role = db.query(Role).filter(Role.code == role_code).first()
    if role is None:
        raise HTTPException(status_code=404, detail="الدور الإداري غير موجود")
    return {"role_code": role.code, "permission_codes": sorted(item.code for item in role.permissions)}


@router.put("/roles/{role_code}/permissions")
def update_role_permissions(
    role_code: str,
    permission_codes: list[str] = Body(..., embed=True),
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(get_current_owner),
):
    _require_current_owner(db, current_user, lock=True)
    role = db.query(Role).filter(Role.code == role_code).with_for_update().first()
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
    previous_codes = sorted(item.code for item in role.permissions)
    role.permissions = permissions
    record_audit(db, current_user, "role.permissions_updated", "role", f"تعديل صلاحيات الدور: {role.name}", entity_id=role.id, details={"before": previous_codes, "after": sorted(item.code for item in permissions)})
    db.commit()
    return {"role_code": role.code, "permission_codes": sorted(item.code for item in permissions)}
