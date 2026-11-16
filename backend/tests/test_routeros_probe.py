from app.services import routeros_probe


class FakeResource:
    def __init__(self, rows):
        self.rows = rows

    def get(self):
        return self.rows


class FakeApi:
    def get_resource(self, path):
        if path == "/system/resource":
            return FakeResource([{
                "version": "7.16.2",
                "board-name": "hAP ax3",
                "architecture-name": "arm64",
                "uptime": "2d3h",
                "cpu-load": "7",
            }])
        if path == "/system/identity":
            return FakeResource([{"name": "edge-router"}])
        raise AssertionError(f"Unexpected RouterOS resource: {path}")


class FakePool:
    instances = []

    def __init__(self, host, **kwargs):
        self.host = host
        self.kwargs = kwargs
        self.socket_timeout = None
        self.connected = False
        self.disconnected = False
        self.__class__.instances.append(self)

    def get_api(self):
        self.connected = True
        return FakeApi()

    def disconnect(self):
        self.disconnected = True
        self.connected = False


def test_probe_routeros_system_reads_metadata_over_tls(monkeypatch):
    FakePool.instances.clear()
    monkeypatch.setattr(routeros_probe.routeros_api, "RouterOsApiPool", FakePool)

    result = routeros_probe.probe_routeros_system(
        host="192.0.2.1",
        port=8729,
        username="readonly",
        password="not-a-real-secret",
    )

    assert result["connected"] is True
    assert result["identity"] == "edge-router"
    assert result["version"] == "7.16.2"
    assert result["cpu_load"] == "7"
    assert result["secure"] is True
    assert result["warnings"] == []
    pool = FakePool.instances[-1]
    assert pool.kwargs["use_ssl"] is True
    assert pool.kwargs["ssl_verify"] is True
    assert pool.disconnected is True


def test_probe_routeros_system_warns_for_plain_api(monkeypatch):
    FakePool.instances.clear()
    monkeypatch.setattr(routeros_probe.routeros_api, "RouterOsApiPool", FakePool)

    result = routeros_probe.probe_routeros_system(
        host="192.0.2.1",
        port=8728,
        username="readonly",
        password="not-a-real-secret",
    )

    assert result["secure"] is False
    assert result["warnings"]
    assert FakePool.instances[-1].kwargs["use_ssl"] is False


def test_probe_routeros_system_hides_connection_exception(monkeypatch):
    class FailingPool(FakePool):
        def get_api(self):
            raise RuntimeError("sensitive connection detail")

    monkeypatch.setattr(routeros_probe.routeros_api, "RouterOsApiPool", FailingPool)

    try:
        routeros_probe.probe_routeros_system(
            host="192.0.2.1",
            port=8729,
            username="readonly",
            password="not-a-real-secret",
        )
    except routeros_probe.RouterConnectionError as exc:
        assert "sensitive connection detail" not in str(exc)
    else:
        raise AssertionError("Expected a safe RouterConnectionError")


def test_router_connection_endpoint_uses_saved_credentials_read_only(owner_client, monkeypatch):
    client, headers, _ = owner_client
    created = client.post(
        "/api/v1/routers",
        headers=headers,
        json={
            "name": "CI Router Probe",
            "nas_identifier": "ci-probe-" + __import__("secrets").token_hex(4),
            "management_host": "192.0.2.10",
            "radius_client_address": "192.0.2.10",
            "api_port": 8729,
            "api_username": "readonly",
            "api_secret": "test-router-api-password",
            "radius_secret": "test-radius-shared-secret",
        },
    )
    assert created.status_code == 201, created.text
    router_id = created.json()["id"]
    observed = {}

    def fake_probe(**kwargs):
        observed.update(kwargs)
        return {
            "identity": "ci-edge",
            "version": "7.16.2",
            "board_name": "hAP ax3",
            "architecture_name": "arm64",
            "uptime": "1d",
            "cpu_load": "3",
            "connected": True,
            "secure": True,
            "warnings": [],
        }

    monkeypatch.setattr("app.api.routers.probe_routeros_system", fake_probe)
    response = client.post(
        f"/api/v1/routers/{router_id}/test-connection",
        headers=headers,
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["connected"] is True
    assert payload["read_only"] is True
    assert payload["identity"] == "ci-edge"
    assert observed["host"] == "192.0.2.10"
    assert observed["port"] == 8729
    assert observed["username"] == "readonly"
    assert observed["password"] == "test-router-api-password"
