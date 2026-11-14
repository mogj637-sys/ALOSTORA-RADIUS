import argparse
from getpass import getpass

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.auth import AdminUser, Role
from app.security import hash_password


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an ALOSTORA-RADIUS administrator.")
    parser.add_argument("--username", required=True)
    parser.add_argument("--display-name", required=True)
    args = parser.parse_args()

    password = getpass("New password (minimum 12 characters): ")
    confirmation = getpass("Confirm password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match.")

    try:
        password_hash = hash_password(password)
    except ValueError as exc:
        raise SystemExit(str(exc))

    db: Session = SessionLocal()
    try:
        if db.query(AdminUser).filter_by(username=args.username).first():
            raise SystemExit("This username already exists.")

        owner_role = db.query(Role).filter_by(code="owner").first()
        if owner_role is None:
            owner_role = Role(
                code="owner",
                name="مدير النظام",
                description="صلاحية إدارة كاملة للنظام",
            )
            db.add(owner_role)
            db.flush()

        user = AdminUser(
            username=args.username,
            display_name=args.display_name,
            password_hash=password_hash,
            is_active=True,
            roles=[owner_role],
        )
        db.add(user)
        db.commit()
        print(f"Administrator '{args.username}' created.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
