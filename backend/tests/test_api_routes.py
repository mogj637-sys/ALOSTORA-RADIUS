from app.main import app


def test_initial_api_routes_are_registered():
    paths = set(app.openapi()["paths"])
    assert "/health" in paths
    assert "/health/ready" in paths
    assert "/api/v1/auth/login" in paths
    assert "/api/v1/auth/me" in paths
    assert "/api/v1/plans" in paths
    assert "/api/v1/cards" in paths
    assert "/api/v1/cards/single" in paths
    assert "/api/v1/cards/batch" in paths
