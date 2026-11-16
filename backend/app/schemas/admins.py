from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class AdminPermissionOverride(BaseModel):
    permission_code: str = Field(min_length=3, max_length=100)
    allowed: bool


class AdminRoleResponse(BaseModel):
    code: str
    name: str
    description: str | None = None


class AdminUserResponse(BaseModel):
    id: int
    username: str
    display_name: str
    is_active: bool
    roles: list[str]
    point_of_sale_ids: list[int] = Field(default_factory=list)
    card_visibility: Literal["all", "assigned", "search_any"] = "search_any"
    permission_overrides: list[AdminPermissionOverride] = Field(default_factory=list)
    last_login_at: datetime | None = None
    created_at: datetime


class AdminUserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=80, pattern=r"^[A-Za-z0-9_.-]+$")
    display_name: str = Field(min_length=2, max_length=150)
    password: str = Field(min_length=12, max_length=256)
    role_codes: list[str] = Field(min_length=1)
    point_of_sale_ids: list[int] = Field(default_factory=list)
    card_visibility: Literal["all", "assigned", "search_any"] = "search_any"
    permission_overrides: list[AdminPermissionOverride] = Field(default_factory=list)

    @field_validator("role_codes")
    @classmethod
    def unique_roles(cls, value: list[str]) -> list[str]:
        normalized = list(dict.fromkeys(code.strip().lower() for code in value if code.strip()))
        if not normalized:
            raise ValueError("يجب اختيار دور واحد على الأقل")
        return normalized


class AdminUserUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=2, max_length=150)
    password: str | None = Field(default=None, min_length=12, max_length=256)
    role_codes: list[str] | None = Field(default=None, min_length=1)
    is_active: bool | None = None
    point_of_sale_ids: list[int] | None = None
    card_visibility: Literal["all", "assigned", "search_any"] | None = None
    permission_overrides: list[AdminPermissionOverride] | None = None

    @field_validator("role_codes")
    @classmethod
    def unique_roles(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        normalized = list(dict.fromkeys(code.strip().lower() for code in value if code.strip()))
        if not normalized:
            raise ValueError("يجب اختيار دور واحد على الأقل")
        return normalized

class AdminRoleCreate(BaseModel):
    code: str = Field(min_length=3, max_length=60, pattern=r"^[a-z][a-z0-9_]+$")
    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=500)

