from datetime import datetime

from pydantic import BaseModel, Field, field_validator


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
    last_login_at: datetime | None = None
    created_at: datetime


class AdminUserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=80, pattern=r"^[A-Za-z0-9_.-]+$")
    display_name: str = Field(min_length=2, max_length=150)
    password: str = Field(min_length=12, max_length=256)
    role_codes: list[str] = Field(min_length=1)

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

    @field_validator("role_codes")
    @classmethod
    def unique_roles(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        normalized = list(dict.fromkeys(code.strip().lower() for code in value if code.strip()))
        if not normalized:
            raise ValueError("يجب اختيار دور واحد على الأقل")
        return normalized
