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


def _count_only(
    api: Any,
    path: str,
    query: dict[str, str] | None = None,
) -> int:
    # RouterOS print count-only returns a scalar count in the 'ret' field.
    # Query terms are applied by the router before any record body is returned.
    # This is especially important before an exact-user read: if the router
    # ignores the filter, the count exposes that without downloading the list.
    params = dict(query or {})
    params["count-only"] = ""
    result = api.get_resource(path).call("print", params)
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


def _query_one(api: Any, path: str, field: str, value: str, properties: str) -> dict[str, Any] | None:
    query = {f"?{field}": value}
    exact_count = _count_only(api, path, query)
    if exact_count == 0:
        return None
    if exact_count != 1:
        raise UserManagerConnectionError(
            "أعاد استعلام العلاقة أكثر من سجل مطابق؛ أوقف القراءة قبل تنزيل التفاصيل."
        )
    rows = api.get_resource(path).call(
        "print",
        {**query, ".proplist": properties},
    )
    if not isinstance(rows, list):
        raise UserManagerConnectionError("أعاد User Manager استجابة غير متوقعة أثناء قراءة علاقة البروفايل.")
    if len(rows) > 1:
        raise UserManagerConnectionError("أعاد User Manager أكثر من سجل مطابق لاسم محدد؛ أوقف القراءة.")
    if not rows:
        return None
    row = rows[0]
    if not isinstance(row, dict) or str(row.get(field, "")) != value:
        raise UserManagerConnectionError("لم تتطابق نتيجة علاقة البروفايل مع القيمة المطلوبة.")
    return row


def inspect_user_manager_user(
    *,
    host: str,
    port: int,
    username: str,
    password: str,
    target_username: str,
    timeout_seconds: float = 8.0,
) -> dict[str, Any] | None:
    """Read one exact user and its directly related profile/limitations.

    All reads are exact RouterOS-side queries with explicit property lists.
    No password, bulk user list, or write operation is requested.
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

        user_path = "/tool/user-manager/user"
        exact_count = _count_only(
            api,
            user_path,
            {"?username": target_username},
        )
        if exact_count == 0:
            return None
        if exact_count != 1:
            raise UserManagerConnectionError(
                "أعاد الاستعلام أكثر من سجل أو لم يثبت تطابقاً واحداً؛ أوقف الفحص دون تنزيل تفاصيل القائمة."
            )

        rows = api.get_resource(user_path).call(
            "print",
            {
                "?username": target_username,
                ".proplist": ".id,username,customer,disabled,actual-profile,shared-users,uptime-used,download-used,upload-used,last-seen,active-sessions",
            },
        )
        if not isinstance(rows, list):
            raise UserManagerConnectionError("أعاد User Manager استجابة غير متوقعة عند فحص المستخدم.")
        if len(rows) > 1:
            raise UserManagerConnectionError("أعاد البحث أكثر من سجل مطابق؛ أوقف الفحص لتجنب اختيار سجل غير صحيح.")
        if not rows:
            return None

        row = rows[0]
        if not isinstance(row, dict) or str(row.get("username", "")) != target_username:
            raise UserManagerConnectionError("لم تتطابق نتيجة البحث مع اسم المستخدم المطلوب؛ أوقف الفحص.")

        profile_name = str(row.get("actual-profile") or "").strip()
        profile: dict[str, Any] | None = None
        limitations: list[dict[str, Any]] = []
        relation_warnings: list[str] = []
        if profile_name:
            profile = _query_one(
                api,
                "/tool/user-manager/profile",
                "name",
                profile_name,
                "name,validity,starts-when,price,override-shared-users,comment",
            )
            if profile is None:
                relation_warnings.append("لم يُعثر على البروفايل الفعلي المشار إليه في سجل الكرت.")

            relation_path = "/tool/user-manager/profile/profile-limitation"
            relation_count = _count_only(api, relation_path, {"?profile": profile_name})
            if relation_count > 100:
                raise UserManagerConnectionError(
                    "عدد قيود البروفايل تجاوز حد القراءة التشخيصية الآمن؛ أوقف القراءة قبل تنزيل التفاصيل."
                )
            relation_rows = api.get_resource(relation_path).call(
                "print",
                {
                    "?profile": profile_name,
                    ".proplist": "profile,limitation",
                },
            )
            if not isinstance(relation_rows, list):
                raise UserManagerConnectionError("تعذر قراءة قيود البروفايل المرتبط بالكرت.")
            if len(relation_rows) != relation_count:
                raise UserManagerConnectionError(
                    "تغير عدد قيود البروفايل أثناء الفحص؛ أوقف القراءة لتجنب نتيجة جزئية."
                )
            for relation in relation_rows:
                if not isinstance(relation, dict) or str(relation.get("profile", "")) != profile_name:
                    raise UserManagerConnectionError("نتيجة ربط القيود لا تطابق البروفايل المطلوب.")
                limitation_name = str(relation.get("limitation") or "").strip()
                if not limitation_name:
                    continue
                limitation = _query_one(
                    api,
                    "/tool/user-manager/limitation",
                    "name",
                    limitation_name,
                    "name,uptime-limit,download-limit,upload-limit,transfer-limit,rate-limit-rx,rate-limit-tx,group",
                )
                if limitation is None:
                    relation_warnings.append(f"القيد المرتبط غير موجود أو غير متاح: {limitation_name}")
                else:
                    limitations.append(limitation)

        return {
            "external_id": str(row.get(".id")) if row.get(".id") is not None else None,
            "username": target_username,
            "customer": row.get("customer"),
            "disabled": row.get("disabled"),
            "actual_profile": profile_name or None,
            "shared_users": row.get("shared-users"),
            "usage": {
                "uptime_used": row.get("uptime-used"),
                "download_used_bytes": row.get("download-used"),
                "upload_used_bytes": row.get("upload-used"),
                "last_seen": row.get("last-seen"),
                "active_sessions": row.get("active-sessions"),
                "missing_fields_are_unknown": True,
            },
            "profile": profile,
            "limitations": limitations,
            "warnings": relation_warnings,
        }
    except UserManagerConnectionError:
        raise
    except Exception as exc:
        raise UserManagerConnectionError(
            "تعذر قراءة سجل المستخدم أو علاقات البروفايل من User Manager. تحقق من صلاحيات القراءة وحقول الإصدار."
        ) from exc
    finally:
        if api is not None or getattr(pool, "connected", False):
            try:
                pool.disconnect()
            except Exception:
                pass
