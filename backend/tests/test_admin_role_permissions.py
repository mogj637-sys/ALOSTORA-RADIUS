import secrets

from app.db.session import SessionLocal
from app.models.auth import AdminUser, Role


def test_owner_can_create_custom_role_and_assign_all_pos_permissions(owner_client):
    client, headers, _ = owner_client
    role_code = "ci_pos_" + secrets.token_hex(4)
    username = "ci_staff_" + secrets.token_hex(4)
    role_id = None
    user_id = None

    try:
        created_role = client.post(
            "/api/v1/admins/roles",
            headers=headers,
            json={
                "code": role_code,
                "name": "موظف نقاط البيع",
                "description": "الوصول إلى جميع نقاط البيع دون صلاحيات مالية",
            },
        )
        assert created_role.status_code == 201
        assert created_role.json()["code"] == role_code

        permissions = ["pos.view", "cards.view", "printing.manage"]
        updated = client.put(
            f"/api/v1/admins/roles/{role_code}/permissions",
            headers=headers,
            json={"permission_codes": permissions},
        )
        assert updated.status_code == 200
        assert set(updated.json()["permission_codes"]) == set(permissions)

        created_user = client.post(
            "/api/v1/admins",
            headers=headers,
            json={
                "username": username,
                "display_name": "موظف نقاط البيع",
                "password": "ci-staff-password-123",
                "role_codes": [role_code],
            },
        )
        assert created_user.status_code == 201
        assert created_user.json()["roles"] == [role_code]

        login = client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": "ci-staff-password-123"},
        )
        assert login.status_code == 200
        staff_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        identity = client.get("/api/v1/auth/me", headers=staff_headers)
        assert identity.status_code == 200
        assert set(identity.json()["permissions"]) == set(permissions)

        # POS staff can list all registered points, but cannot create or edit them.
        points = client.get("/api/v1/points-of-sale", headers=staff_headers)
        assert points.status_code == 200
        forbidden = client.post(
            "/api/v1/points-of-sale",
            headers=staff_headers,
            json={"code": "CI-FORBIDDEN", "name": "Forbidden"},
        )
        assert forbidden.status_code == 403

        db = SessionLocal()
        user = db.query(AdminUser).filter_by(username=username).first()
        role = db.query(Role).filter_by(code=role_code).first()
        user_id = user.id if user else None
        role_id = role.id if role else None
        db.close()
    finally:
        db = SessionLocal()
        user = db.query(AdminUser).filter_by(username=username).first()
        if user is not None:
            user.roles = []
            db.delete(user)
        role = db.query(Role).filter_by(code=role_code).first()
        if role is not None:
            db.delete(role)
        db.commit()
        db.close()
