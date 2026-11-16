from __future__ import annotations

from typing import Any

import routeros_api


class RouterConnectionError(RuntimeError):
    """Safe connection failure without exposing credentials or library details."""


def probe_routeros_system(
    *,
    host: str,
    port: int,
    username: str,
    password: str,
    timeout_seconds: float = 8.0,
) -> dict[str, Any]:
    """Read basic RouterOS system identity/resource metadata without making changes."""
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
        resources = api.get_resource("/system/resource").get()
        identities = api.get_resource("/system/identity").get()
        if not resources:
            raise RouterConnectionError("لم يُرجع الراوتر معلومات النظام.")
        resource = resources[0]
        identity = identities[0] if identities else {}
        return {
            "identity": identity.get("name"),
            "version": resource.get("version"),
            "board_name": resource.get("board-name"),
            "architecture_name": resource.get("architecture-name"),
            "uptime": resource.get("uptime"),
            "cpu_load": resource.get("cpu-load"),
            "connected": True,
            "secure": use_ssl,
            "warnings": [] if use_ssl else [
                "الاتصال يستخدم API العادي دون TLS؛ استخدم شبكة إدارة موثوقة أو فعّل API-SSL."
            ],
        }
    except RouterConnectionError:
        raise
    except Exception as exc:
        raise RouterConnectionError(
            "تعذر الاتصال بالراوتر أو قراءة معلوماته. تحقق من العنوان والمنفذ وبيانات API وصلاحيات المستخدم والجدار الناري."
        ) from exc
    finally:
        if api is not None or getattr(pool, "connected", False):
            try:
                pool.disconnect()
            except Exception:
                pass
