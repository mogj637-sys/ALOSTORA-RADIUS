from app.models.auth import AdminUser


def is_owner(user: AdminUser) -> bool:
    return any(role.code == "owner" for role in user.roles)


def effective_permission_codes(user: AdminUser) -> set[str]:
    if is_owner(user):
        return {"*"}
    granted = {
        permission.code
        for role in user.roles
        for permission in role.permissions
    }
    for override in user.permission_overrides:
        if override.allowed:
            granted.add(override.permission.code)
        else:
            granted.discard(override.permission.code)
    return granted


def has_permission(user: AdminUser, permission_code: str) -> bool:
    if is_owner(user):
        return True
    overrides = {
        item.permission.code: item.allowed
        for item in user.permission_overrides
    }
    if permission_code in overrides:
        return overrides[permission_code]
    granted = effective_permission_codes(user)
    if permission_code in granted:
        return True
    module, _, action = permission_code.partition(".")
    if action == "view":
        if f"{module}.manage" in granted or (
            module == "sessions" and "sessions.disconnect" in granted
        ):
            return True
    if action in {"create", "update", "delete", "reprint"}:
        if f"{module}.manage" in overrides:
            return overrides[f"{module}.manage"]
        return f"{module}.manage" in granted
    # Credential disclosure is intentionally never implied by a broad manage grant.
    return False


def card_visibility(user: AdminUser) -> str:
    return "all" if is_owner(user) else user.card_visibility
