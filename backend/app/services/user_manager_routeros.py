from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import routeros_api


class UserManagerConnectionError(RuntimeError):
    """Safe, user-facing connection failure without router credentials."""


@dataclass(frozen=True)
class RouterProbe:
    identity: str | None
    version: str | None
    board_name: str | None
    architecture_name: str | None
    uptime: str | None
    user_manager_available: bool
    resources: dict[str, dict[str, Any]]
    warnings: list[str]


# These are read-only RouterOS v6 User Manager menu paths. A missing menu is
# reported as unavailable rather than treated as an empty resource.
USER_MANAGER_RESOURCES = {
    "users": "/tool/user-manager/user",
    "profiles": "/tool/user-manager/profile",
    "limitations": "/tool/user-manager/limitation",
    "profile_limitations": "/tool/user-manager/profile/profile-limitation",
    "sessions": "/tool/user-manager/session",
    "customers": "/tool/user-manager/customer",
}


def _first(items: list[dict[str, Any]], key: str) -> str | None:
    if not items:
        return None
    value = items[0].get(key)
    return str(value) if value is not None else None


def _count_only(api: Any, path: str) -> int:
    # RouterOS print count-only returns a scalar count in the 'ret' field.
    # This avoids loading thousands of records into the API worker.
    result = api.get_resource(path).call("print", {"count-only": ""})
    if isinstance(result, dict):
        value = result.get("ret")
        if value is not None:
            return int(value)
    if isinstance(result, list):
        for row in result:
            if isinstance(row, dict) and row.get("ret") is not None:
                return int(row["ret"])
    raise ValueError("RouterOS did not return a count-only result")


def inspect_routeros_user_manager(
    *,
    host: str,
    port: int,
    username: str,
    password: str,
    timeout_seconds: float = 8.0,
) -> RouterProbe:
    """Connect and inspect metadata/counts only. Never changes router state."""
    use_ssl = port == 8729
    pool = routeros_api.RouterOsApiPool(
        host,
        username=username,
        password=password,
        port=port,
        plaintext_login=True,  # RouterOS v6.43+ login flow
        use_ssl=use_ssl,
        ssl_verify=True,
        ssl_verify_hostname=True,
    )
    pool.socket_timeout = timeout_seconds
    api = None
    try:
        api = pool.get_api()
        system = api.get_resource("/system/resource").get()
        identity = api.get_resource("/system/identity").get()
        packages = api.get_resource("/system/package").get()
        version = _first(system, "version")
        if not version or not version.startswith("6."):
            raise UserManagerConnectionError(
                "هذا الموصل مخصص حالياً لـ RouterOS v6؛ دعم v7 يحتاج موصلاً واختبارات منفصلة."
            )
        package_names = {
            str(row.get("name", "")).lower()
            for row in packages
            if isinstance(row, dict)
        }
        has_um_package = any("user-manager" in name for name in package_names)

        resources: dict[str, dict[str, Any]] = {}
        warnings: list[str] = []
        for key, path in USER_MANAGER_RESOURCES.items():
            try:
                resources[key] = {"available": True, "count": _count_only(api, path)}
            except Exception:
                resources[key] = {"available": False, "count": None}
                warnings.append(f"تعذر قراءة مورد User Manager: {key}")

        user_manager_available = has_um_package and resources["users"]["available"]
        if not has_um_package:
            warnings.append("حزمة User Manager غير ظاهرة ضمن الحزم المثبتة")
        if not resources["users"]["available"]:
            warnings.append("قائمة مستخدمي User Manager غير متاحة لهذا الحساب أو الإصدار")
        if not use_ssl:
            warnings.append(
                "الاتصال يستخدم API العادي دون TLS؛ استخدم شبكة إدارة موثوقة أو فعّل API-SSL"
            )

        return RouterProbe(
            identity=_first(identity, "name"),
            version=version,
            board_name=_first(system, "board-name"),
            architecture_name=_first(system, "architecture-name"),
            uptime=_first(system, "uptime"),
            user_manager_available=user_manager_available,
            resources=resources,
            warnings=warnings,
        )
    except UserManagerConnectionError:
        raise
    except Exception as exc:
        # Do not return library exception strings: some implementations include
        # request details. Keep the original exception only for server logs.
        raise UserManagerConnectionError(
            "تعذر الاتصال بالراوتر أو فشل التحقق من بيانات API. تحقق من العنوان والمنفذ والصلاحيات والجدار الناري."
        ) from exc
    finally:
        if api is not None or getattr(pool, "connected", False):
            try:
                pool.disconnect()
            except Exception:
                pass


def inspect_user_manager_user(
    *,
    host: str,
    port: int,
    username: str,
    password: str,
    target_username: str,
    timeout_seconds: float = 8.0,
) -> dict[str, Any] | None:
    """Read one exact User Manager username using RouterOS-side query filtering.

    Passwords and other credential fields are deliberately excluded from
    .proplist and from the returned object. This is a diagnostic lookup only;
    it does not create, update, or import a card.
    """
    if not target_username or len(target_username) > 120:
        raise ValueError("Invalid User Manager username")

    use_ssl = port == 8729
    pool = routeros_api.RouterOsApiPool(
        host,
        username=username,
        password=password,
        port=port,
        plaintext_login=True,
        use_ssl=use_ssl,
        ssl_verify=True,
        ssl_verify_hostname=True,
    )
    pool.socket_timeout = timeout_seconds
    api = None
    try:
        api = pool.get_api()
        system = api.get_resource("/system/resource").get()
        version = _first(system, "version")
        if not version or not version.startswith("6."):
            raise UserManagerConnectionError(
                "هذا الفحص مخصص حالياً لـ RouterOS v6؛ دعم v7 يحتاج موصلاً واختبارات منفصلة."
            )

        # RouterOS executes the exact-match query on the device. Keep the
        # returned property list intentionally small and never request password.
        rows = api.get_resource("/tool/user-manager/user").call(
            "print",
            {
                "?username": target_username,
                ".proplist": ".id,username,customer,disabled,actual-profile,shared-users",
            },
        )
        if not isinstance(rows, list):
            raise UserManagerConnectionError(
                "أعاد User Manager استجابة غير متوقعة عند فحص المستخدم."
            )
        if len(rows) > 1:
            raise UserManagerConnectionError(
                "أعاد البحث أكثر من سجل مطابق؛ أوقف الفحص لتجنب اختيار سجل غير صحيح."
            )
        if not rows:
            return None

        row = rows[0]
        if not isinstance(row, dict) or str(row.get("username", "")) != target_username:
            raise UserManagerConnectionError(
                "لم تتطابق نتيجة البحث مع اسم المستخدم المطلوب؛ أوقف الفحص."
            )
        return {
            "external_id": str(row.get(".id")) if row.get(".id") is not None else None,
            "username": target_username,
            "customer": row.get("customer"),
            "disabled": row.get("disabled"),
            "actual_profile": row.get("actual-profile"),
            "shared_users": row.get("shared-users"),
        }
    except UserManagerConnectionError:
        raise
    except Exception as exc:
        raise UserManagerConnectionError(
            "تعذر قراءة سجل المستخدم المحدد من User Manager. تحقق من صلاحيات القراءة وإصدار الجهاز."
        ) from exc
    finally:
        if api is not None or getattr(pool, "connected", False):
            try:
                pool.disconnect()
            except Exception:
                pass
