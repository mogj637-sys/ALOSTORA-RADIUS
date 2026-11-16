from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Table, Column, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.core import TimestampMixin

user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", ForeignKey("admin_users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)


admin_user_points_of_sale = Table(
    "admin_user_points_of_sale",
    Base.metadata,
    Column("user_id", ForeignKey("admin_users.id", ondelete="CASCADE"), primary_key=True),
    Column("point_of_sale_id", ForeignKey("points_of_sale.id", ondelete="CASCADE"), primary_key=True),
)


role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)


class AdminUser(TimestampMixin, Base):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(150), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    roles = relationship("Role", secondary=user_roles, back_populates="users", lazy="selectin")
    point_of_sales = relationship("PointOfSale", secondary=admin_user_points_of_sale, lazy="selectin")
    card_visibility: Mapped[str] = mapped_column(String(20), nullable=False, default="search_any")
    permission_overrides = relationship(
        "AdminUserPermissionOverride",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class Role(TimestampMixin, Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    users = relationship("AdminUser", secondary=user_roles, back_populates="roles")
    permissions = relationship("Permission", secondary=role_permissions, back_populates="roles", lazy="selectin")


class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    module: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    roles = relationship("Role", secondary=role_permissions, back_populates="permissions")
    user_overrides = relationship("AdminUserPermissionOverride", back_populates="permission")


class AdminUserPermissionOverride(Base):
    __tablename__ = "admin_user_permission_overrides"

    user_id: Mapped[int] = mapped_column(ForeignKey("admin_users.id", ondelete="CASCADE"), primary_key=True)
    permission_id: Mapped[int] = mapped_column(ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True)
    allowed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    user = relationship("AdminUser", back_populates="permission_overrides")
    permission = relationship("Permission", back_populates="user_overrides")


