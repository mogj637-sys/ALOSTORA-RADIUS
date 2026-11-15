from types import SimpleNamespace

import pytest

from app.services import user_manager_routeros as adapter


class FakeResource:
    def __init__(self, rows=None, count=None, error=None):
        self.rows = rows or []
        self.count = count
        self.error = error

    def get(self):
        if self.error:
            raise self.error
        return self.rows

    def call(self, command, params):
        assert command == "print"
        assert params == {"count-only": ""}
        if self.error:
            raise self.error
        return [{"ret": str(self.count)}]


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


def test_v7_is_not_misreported_as_legacy_v6(monkeypatch):
    monkeypatch.setattr(adapter.routeros_api, "RouterOsApiPool", FakePool)
    api = FakeApi(_fake_resources(version="7.18"))
    monkeypatch.setattr(FakePool, "get_api", lambda self: (setattr(self, "connected", True) or api))

    with pytest.raises(adapter.UserManagerConnectionError, match="RouterOS v6"):
        adapter.inspect_routeros_user_manager(
            host="192.0.2.10", port=8728, username="reader", password="secret"
        )


def test_missing_user_manager_package_is_warning_not_empty_inventory(monkeypatch):
    monkeypatch.setattr(adapter.routeros_api, "RouterOsApiPool", FakePool)
    api = FakeApi(_fake_resources(package=False))
    monkeypatch.setattr(FakePool, "get_api", lambda self: (setattr(self, "connected", True) or api))

    result = adapter.inspect_routeros_user_manager(
        host="192.0.2.10", port=8728, username="reader", password="secret"
    )

    assert result.user_manager_available is False
    assert any("حزمة User Manager" in warning for warning in result.warnings)
    assert any("دون TLS" in warning for warning in result.warnings)


def test_api_error_is_sanitized(monkeypatch):
    monkeypatch.setattr(adapter.routeros_api, "RouterOsApiPool", FakePool)

    def fail(self):
        self.connected = True
        raise RuntimeError("sensitive router command details")

    monkeypatch.setattr(FakePool, "get_api", fail)
    with pytest.raises(adapter.UserManagerConnectionError) as error:
        adapter.inspect_routeros_user_manager(
            host="192.0.2.10", port=8728, username="reader", password="secret"
        )
    assert "sensitive router command details" not in str(error.value)
