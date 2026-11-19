from types import SimpleNamespace

import pytest

from app.services import user_manager_routeros as adapter


class FakeResponse(list):
    def __init__(self, rows=None, done_message=None):
        super().__init__(rows or [])
        self.done_message = done_message or {}


class FakeResource:
    def __init__(self, rows=None, count=None, error=None):
        self.rows = rows or []
        self.count = len(self.rows) if count is None else count
        self.error = error
        self.calls = []

    def get(self):
        if self.error:
            raise self.error
        return self.rows

    def call(self, command, params=None, queries=None):
        assert command == "print"
        if self.error:
            raise self.error
        params = dict(params or {})
        queries = dict(queries or {})
        self.calls.append((command, params, queries))
        if "count-only" in params:
            assert params["count-only"] == ""
            return FakeResponse(done_message={"ret": str(self.count)})
        self.last_params = params
        self.last_queries = queries
        return FakeResponse(self.rows)


class FakeApi:
    def __init__(self, resources):
        self.resources = resources

    def get_resource(self, path):
        if path not in self.resources:
            raise RuntimeError("missing")
        return self.resources[path]


class FakePool:
    last = None

    def __init__(self, host, **kwargs):
        self.host = host
        self.kwargs = kwargs
        self.socket_timeout = None
        self.connected = False
        self.disconnected = False
        FakePool.last = self

    def get_api(self):
        self.connected = True
        return self.api

    def disconnect(self):
        self.disconnected = True
        self.connected = False


def _fake_resources(version="6.49.23 (stable)", package=True):
    packages = [{"name": "user-manager"}] if package else [{"name": "system"}]
    counts = {
        "/tool/user-manager/user": 12,
        "/tool/user-manager/profile": 3,
        "/tool/user-manager/limitation": 2,
        "/tool/user-manager/profile/profile-limitation": 4,
        "/tool/user-manager/session": 8,
        "/tool/user-manager/customer": 1,
    }
    resources = {
        "/system/resource": FakeResource([{
            "version": version,
            "board-name": "RB2011UiAS-2HnD",
            "architecture-name": "mipsbe",
            "uptime": "1d2h",
        }]),
        "/system/identity": FakeResource([{"name": "radius-test"}]),
        "/system/package": FakeResource(packages),
    }
    resources.update({path: FakeResource(count=count) for path, count in counts.items()})
    return resources


def test_v6_probe_only_reads_metadata_and_count_only(monkeypatch):
    pool_type = FakePool
    monkeypatch.setattr(adapter.routeros_api, "RouterOsApiPool", pool_type)
    resources = _fake_resources()
    api = FakeApi(resources)
    monkeypatch.setattr(FakePool, "get_api", lambda self: (setattr(self, "connected", True) or api))

    result = adapter.inspect_routeros_user_manager(
        host="192.0.2.10", port=8729, username="reader", password="secret"
    )

    assert result.version.startswith("6.49.23")
    assert result.user_manager_available is True
    assert result.resources["users"]["count"] == 12
    assert result.resources["profile_limitations"]["count"] == 4
    assert result.resources["customers"]["count"] == 1
    assert FakePool.last.kwargs["use_ssl"] is True
    assert FakePool.last.kwargs["plaintext_login"] is True
    assert FakePool.last.socket_timeout == 8.0
    assert FakePool.last.disconnected is True



def test_count_only_uses_empty_string_compatible_with_pinned_routeros_resource():
    from routeros_api.api_structure import default_structure
    from routeros_api.resource import RouterOsResource

    class Response:
        done_message = {"ret": "1"}

        def map(self, _function):
            return self

    class Promise:
        def get(self):
            return Response()

    class Communicator:
        def __init__(self):
            self.arguments = None
            self.queries = None

        def call(self, _path, _command, arguments=None, queries=None, additional_queries=()):
            self.arguments = arguments
            self.queries = queries
            return Promise()

    communicator = Communicator()
    resource = RouterOsResource(
        communicator,
        "/tool/user-manager/user",
        default_structure,
    )
    api = SimpleNamespace(get_resource=lambda _path: resource)

    assert adapter._count_only(api, "/tool/user-manager/user", {"?username": "voucher-100"}) == 1
    assert communicator.arguments == {"count-only": b""}
    assert communicator.queries == {"username": b"voucher-100"}



def test_probe_disconnects_socket_when_login_fails_before_connected(monkeypatch):
    monkeypatch.setattr(adapter.routeros_api, "RouterOsApiPool", FakePool)

    def fail_before_connected(self):
        raise RuntimeError("login rejected")

    monkeypatch.setattr(FakePool, "get_api", fail_before_connected)
    with pytest.raises(adapter.UserManagerConnectionError):
        adapter.inspect_routeros_user_manager(
            host="192.0.2.10", port=8729, username="reader", password="secret"
        )

    assert FakePool.last.connected is False
    assert FakePool.last.disconnected is True


def test_user_inspection_disconnects_socket_when_login_fails_before_connected(monkeypatch):
    monkeypatch.setattr(adapter.routeros_api, "RouterOsApiPool", FakePool)

    def fail_before_connected(self):
        raise RuntimeError("login rejected")

    monkeypatch.setattr(FakePool, "get_api", fail_before_connected)
    with pytest.raises(adapter.UserManagerConnectionError):
        adapter.inspect_user_manager_user(
            host="192.0.2.10", port=8729, username="reader",
            password="secret", target_username="voucher-100",
        )

    assert FakePool.last.connected is False
    assert FakePool.last.disconnected is True


def test_v7_is_not_misreported_as_legacy_v6(monkeypatch):
    monkeypatch.setattr(adapter.routeros_api, "RouterOsApiPool", FakePool)
    api = FakeApi(_fake_resources(version="7.18"))
    monkeypatch.setattr(FakePool, "get_api", lambda self: (setattr(self, "connected", True) or api))

    with pytest.raises(adapter.UserManagerConnectionError, match="RouterOS v6"):
        adapter.inspect_routeros_user_manager(
            host="192.0.2.10", port=8729, username="reader", password="secret"
        )


def test_missing_user_manager_package_is_warning_not_empty_inventory(monkeypatch):
    monkeypatch.setattr(adapter.routeros_api, "RouterOsApiPool", FakePool)
    api = FakeApi(_fake_resources(package=False))
    monkeypatch.setattr(FakePool, "get_api", lambda self: (setattr(self, "connected", True) or api))

    result = adapter.inspect_routeros_user_manager(
        host="192.0.2.10", port=8729, username="reader", password="secret"
    )

    assert result.user_manager_available is False
    assert any("حزمة User Manager" in warning for warning in result.warnings)
    assert not any("دون TLS" in warning for warning in result.warnings)


def test_api_error_is_sanitized(monkeypatch):
    monkeypatch.setattr(adapter.routeros_api, "RouterOsApiPool", FakePool)

    def fail(self):
        self.connected = True
        raise RuntimeError("sensitive router command details")

    monkeypatch.setattr(FakePool, "get_api", fail)
    with pytest.raises(adapter.UserManagerConnectionError) as error:
        adapter.inspect_routeros_user_manager(
            host="192.0.2.10", port=8729, username="reader", password="secret"
        )
    assert "sensitive router command details" not in str(error.value)



def test_exact_user_inspection_uses_device_query_and_never_requests_password(monkeypatch):
    monkeypatch.setattr(adapter.routeros_api, "RouterOsApiPool", FakePool)
    resources = _fake_resources()
    user_resource = FakeResource(rows=[{
        ".id": "*A1",
        "username": "voucher-100",
        "customer": "admin",
        "disabled": "false",
        "actual-profile": "basic",
        "shared-users": "1",
        "uptime-used": "2h30m",
        "download-used": "1048576",
        "upload-used": "2048",
        "last-seen": "nov/15/2026 10:00:00",
        "active-sessions": "0",
    }])
    resources["/tool/user-manager/user"] = user_resource
    resources["/tool/user-manager/profile"] = FakeResource(rows=[{
        "name": "basic", "validity": "5d", "starts-when": " first-auth",
        "price": "0", "override-shared-users": "1", "comment": "starter",
    }])
    resources["/tool/user-manager/profile/profile-limitation"] = FakeResource(rows=[
        {"profile": "basic", "limitation": "basic-limit"},
    ])
    resources["/tool/user-manager/limitation"] = FakeResource(rows=[{
        "name": "basic-limit", "uptime-limit": "1d", "download-limit": "800M",
        "upload-limit": "100M", "transfer-limit": "900M",
        "rate-limit-rx": "2M", "rate-limit-tx": "512k", "group": "default",
    }])
    api = FakeApi(resources)
    monkeypatch.setattr(FakePool, "get_api", lambda self: (setattr(self, "connected", True) or api))

    result = adapter.inspect_user_manager_user(
        host="192.0.2.10",
        port=8729,
        username="reader",
        password="secret",
        target_username="voucher-100",
    )

    assert result == {
        "external_id": "*A1",
        "username": "voucher-100",
        "customer": "admin",
        "disabled": "false",
        "actual_profile": "basic",
        "shared_users": "1",
        "usage": {
            "uptime_used": "2h30m",
            "download_used_bytes": "1048576",
            "upload_used_bytes": "2048",
            "last_seen": "nov/15/2026 10:00:00",
            "active_sessions": "0",
            "missing_fields_are_unknown": True,
        },
        "profile": {
            "name": "basic", "validity": "5d", "starts-when": " first-auth",
            "price": "0", "override-shared-users": "1", "comment": "starter",
        },
        "limitations": [{
            "name": "basic-limit", "uptime-limit": "1d", "download-limit": "800M",
            "upload-limit": "100M", "transfer-limit": "900M",
            "rate-limit-rx": "2M", "rate-limit-tx": "512k", "group": "default",
        }],
        "warnings": [],
    }
    assert user_resource.calls[0] == (
        "print", {"count-only": ""}, {"username": "voucher-100"}
    )
    assert user_resource.last_params == {
        ".proplist": ".id,username,customer,disabled,actual-profile,shared-users,uptime-used,download-used,upload-used,last-seen,active-sessions",
    }
    assert user_resource.last_queries == {"username": "voucher-100"}
    assert "password" not in user_resource.last_params[".proplist"]
    assert FakePool.last.disconnected is True


def test_exact_user_inspection_returns_none_when_not_found(monkeypatch):
    monkeypatch.setattr(adapter.routeros_api, "RouterOsApiPool", FakePool)
    resources = _fake_resources()
    resources["/tool/user-manager/user"] = FakeResource(rows=[])
    api = FakeApi(resources)
    monkeypatch.setattr(FakePool, "get_api", lambda self: (setattr(self, "connected", True) or api))

    result = adapter.inspect_user_manager_user(
        host="192.0.2.10",
        port=8729,
        username="reader",
        password="secret",
        target_username="missing-card",
    )

    assert result is None


def test_exact_user_inspection_rejects_unfiltered_or_ambiguous_result(monkeypatch):
    monkeypatch.setattr(adapter.routeros_api, "RouterOsApiPool", FakePool)
    resources = _fake_resources()
    resources["/tool/user-manager/user"] = FakeResource(rows=[
        {"username": "voucher-100"},
        {"username": "voucher-100"},
    ])
    api = FakeApi(resources)
    monkeypatch.setattr(FakePool, "get_api", lambda self: (setattr(self, "connected", True) or api))

    with pytest.raises(adapter.UserManagerConnectionError, match="أكثر من سجل"):
        adapter.inspect_user_manager_user(
            host="192.0.2.10",
            port=8729,
            username="reader",
            password="secret",
            target_username="voucher-100",
        )


def test_exact_user_inspection_rejects_wrong_username_returned_by_query(monkeypatch):
    monkeypatch.setattr(adapter.routeros_api, "RouterOsApiPool", FakePool)
    resources = _fake_resources()
    resources["/tool/user-manager/user"] = FakeResource(rows=[
        {"username": "different-user"},
    ])
    api = FakeApi(resources)
    monkeypatch.setattr(FakePool, "get_api", lambda self: (setattr(self, "connected", True) or api))

    with pytest.raises(adapter.UserManagerConnectionError, match="لم تتطابق"):
        adapter.inspect_user_manager_user(
            host="192.0.2.10",
            port=8729,
            username="reader",
            password="secret",
            target_username="voucher-100",
        )



def test_exact_user_filter_count_prevents_bulk_read_when_router_ignores_query(monkeypatch):
    monkeypatch.setattr(adapter.routeros_api, "RouterOsApiPool", FakePool)
    resources = _fake_resources()
    # Simulate a router/API behavior that ignores ?username and reports the
    # full 30,000-user menu count. The adapter must stop before print details.
    user_resource = FakeResource(rows=[{"username": "voucher-100"}], count=30000)
    resources["/tool/user-manager/user"] = user_resource
    api = FakeApi(resources)
    monkeypatch.setattr(FakePool, "get_api", lambda self: (setattr(self, "connected", True) or api))

    with pytest.raises(adapter.UserManagerConnectionError, match="أكثر من سجل"):
        adapter.inspect_user_manager_user(
            host="192.0.2.10",
            port=8729,
            username="reader",
            password="secret",
            target_username="voucher-100",
        )

    assert user_resource.calls == [
        ("print", {"count-only": ""}, {"username": "voucher-100"})
    ]
    assert FakePool.last.disconnected is True


def test_exact_user_count_zero_skips_detail_print(monkeypatch):
    monkeypatch.setattr(adapter.routeros_api, "RouterOsApiPool", FakePool)
    resources = _fake_resources()
    user_resource = FakeResource(rows=[{"username": "should-not-be-returned"}], count=0)
    resources["/tool/user-manager/user"] = user_resource
    api = FakeApi(resources)
    monkeypatch.setattr(FakePool, "get_api", lambda self: (setattr(self, "connected", True) or api))

    result = adapter.inspect_user_manager_user(
        host="192.0.2.10",
        port=8729,
        username="reader",
        password="secret",
        target_username="missing-card",
    )

    assert result is None
    assert user_resource.calls == [
        ("print", {"count-only": ""}, {"username": "missing-card"})
    ]



def test_profile_relation_count_guard_stops_before_large_detail_read(monkeypatch):
    monkeypatch.setattr(adapter.routeros_api, "RouterOsApiPool", FakePool)
    resources = _fake_resources()
    resources["/tool/user-manager/user"] = FakeResource(rows=[{
        ".id": "*A1",
        "username": "voucher-100",
        "actual-profile": "basic",
    }])
    profile_resource = FakeResource(rows=[{"name": "basic"}])
    resources["/tool/user-manager/profile"] = profile_resource
    relation_resource = FakeResource(
        rows=[{"profile": "basic", "limitation": "lim-1"}],
        count=101,
    )
    resources["/tool/user-manager/profile/profile-limitation"] = relation_resource
    api = FakeApi(resources)
    monkeypatch.setattr(FakePool, "get_api", lambda self: (setattr(self, "connected", True) or api))

    with pytest.raises(adapter.UserManagerConnectionError, match="تجاوز حد القراءة"):
        adapter.inspect_user_manager_user(
            host="192.0.2.10",
            port=8729,
            username="reader",
            password="secret",
            target_username="voucher-100",
        )

    assert relation_resource.calls == [
        ("print", {"count-only": ""}, {"profile": "basic"})
    ]
    assert FakePool.last.disconnected is True


def test_router_probe_rejects_unencrypted_api_before_opening_socket(monkeypatch):
    monkeypatch.setattr(adapter.routeros_api, "RouterOsApiPool", FakePool)
    FakePool.last = None

    with pytest.raises(adapter.UserManagerConnectionError, match="غير المشفر غير مدعوم"):
        adapter.inspect_routeros_user_manager(
            host="192.0.2.10",
            port=8728,
            username="reader",
            password="secret",
            use_ssl=False,
        )

    assert FakePool.last is None




def test_exact_user_inspection_uses_explicit_tls_on_custom_port(monkeypatch):
    monkeypatch.setattr(adapter.routeros_api, "RouterOsApiPool", FakePool)
    resources = _fake_resources()
    resources["/tool/user-manager/user"] = FakeResource(rows=[], count=0)
    api = FakeApi(resources)
    monkeypatch.setattr(
        FakePool, "get_api",
        lambda self: (setattr(self, "connected", True) or api),
    )

    result = adapter.inspect_user_manager_user(
        host="192.0.2.10",
        port=18729,
        username="reader",
        password="secret",
        target_username="missing-card",
        use_ssl=True,
    )

    assert result is None
    assert FakePool.last.kwargs["use_ssl"] is True
    assert FakePool.last.disconnected is True



def test_exact_user_inspection_rejects_unencrypted_api_before_opening_socket(monkeypatch):
    monkeypatch.setattr(adapter.routeros_api, "RouterOsApiPool", FakePool)
    FakePool.last = None

    with pytest.raises(adapter.UserManagerConnectionError, match="غير المشفر غير مدعوم"):
        adapter.inspect_user_manager_user(
            host="192.0.2.10",
            port=8728,
            username="reader",
            password="secret",
            target_username="missing-card",
            use_ssl=False,
        )

    assert FakePool.last is None


def test_nonstandard_api_port_defaults_to_tls_when_not_explicitly_overridden(monkeypatch):
    monkeypatch.setattr(adapter.routeros_api, "RouterOsApiPool", FakePool)
    api = FakeApi(_fake_resources())
    monkeypatch.setattr(
        FakePool, "get_api",
        lambda self: (setattr(self, "connected", True) or api),
    )

    adapter.inspect_routeros_user_manager(
        host="192.0.2.10",
        port=18729,
        username="reader",
        password="secret",
    )

    assert FakePool.last.kwargs["use_ssl"] is True
    assert FakePool.last.disconnected is True



def test_router_probe_rejects_plain_api_port_when_tls_is_unspecified(monkeypatch):
    monkeypatch.setattr(adapter.routeros_api, "RouterOsApiPool", FakePool)
    FakePool.last = None

    with pytest.raises(adapter.UserManagerConnectionError, match="غير المشفر غير مدعوم"):
        adapter.inspect_routeros_user_manager(
            host="192.0.2.10",
            port=8728,
            username="reader",
            password="secret",
        )

    assert FakePool.last is None
