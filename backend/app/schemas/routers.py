from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RouterCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    nas_identifier: str = Field(min_length=1, max_length=150, pattern=r"^[A-Za-z0-9_.:-]+$")
    management_host: str = Field(min_length=1, max_length=255)
    api_port: int = Field(default=8728, ge=1, le=65535)
    api_username: str | None = Field(default=None, max_length=120)
    api_secret: str | None = Field(default=None, min_length=8, max_length=500)
    radius_secret: str = Field(min_length=8, max_length=500)
    routeros_version: str | None = Field(default=None, max_length=30)
    is_active: bool = True

    @model_validator(mode="after")
    def api_credentials_must_be_paired(self) -> Self:
        if bool(self.api_username) != bool(self.api_secret):
            raise ValueError("يجب إدخال اسم مستخدم API وكلمة مروره معاً، أو تركهما فارغين")
        return self


class RouterUpdate(BaseModel):
    name: str = Field(default=None, min_length=2, max_length=120)
    management_host: str = Field(default=None, min_length=1, max_length=255)
    api_port: int = Field(default=None, ge=1, le=65535)
    api_username: str | None = Field(default=None, max_length=120)
    api_secret: str | None = Field(default=None, min_length=8, max_length=500)
    radius_secret: str = Field(default=None, min_length=8, max_length=500)
    routeros_version: str | None = Field(default=None, max_length=30)
    is_active: bool = Field(default=None)

    @model_validator(mode="after")
    def reject_empty_update(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("يجب إرسال حقل واحد على الأقل للتعديل")
        credential_fields = {"api_username", "api_secret"}
        if self.model_fields_set.intersection(credential_fields):
            if not credential_fields.issubset(self.model_fields_set):
                raise ValueError("يجب تحديث اسم مستخدم API وكلمة مروره معاً")
            if bool(self.api_username) != bool(self.api_secret):
                raise ValueError("يجب إدخال بيانات API كاملة أو مسحها معاً")
        return self


class RouterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    nas_identifier: str
    management_host: str
    api_port: int
    api_username: str | None
    routeros_version: str | None
    is_active: bool
    last_seen_at: datetime | None
    created_at: datetime
