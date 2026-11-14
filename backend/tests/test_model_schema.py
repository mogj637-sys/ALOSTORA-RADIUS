from app.db.base import Base
from app.models import Card, Plan, PointOfSale, RadiusSession


def test_core_models_are_registered():
    expected = {
        "plans",
        "points_of_sale",
        "routers",
        "cards",
        "print_jobs",
        "pos_inventory_movements",
        "card_events",
        "radius_sessions",
    }
    assert expected.issubset(set(Base.metadata.tables))


def test_card_schema_has_first_use_and_expiry_fields():
    columns = Card.__table__.columns
    assert "first_used_at" in columns
    assert "expires_at" in columns
    assert "used_seconds" in columns
    assert "upload_bytes" in columns
    assert "download_bytes" in columns


def test_unlimited_plan_limits_are_nullable():
    assert Plan.__table__.columns["data_limit_bytes"].nullable
    assert Plan.__table__.columns["session_time_limit_seconds"].nullable
    assert Plan.__table__.columns["validity_period_seconds"].nullable


def test_point_of_sale_and_radius_session_models_exist():
    assert PointOfSale.__tablename__ == "points_of_sale"
    assert RadiusSession.__tablename__ == "radius_sessions"
