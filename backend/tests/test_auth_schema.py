from app.db.base import Base
from app.models.auth import AdminUser, Role


def test_admin_auth_tables_are_registered():
    assert "admin_users" in Base.metadata.tables
    assert "roles" in Base.metadata.tables
    assert "user_roles" in Base.metadata.tables


def test_admin_user_password_is_stored_as_hash_field():
    assert "password_hash" in AdminUser.__table__.columns
    assert "username" in AdminUser.__table__.columns
    assert Role.__tablename__ == "roles"
