from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class PlanCreate(BaseModel):
    code: str = Field(min_length=2, max_length=50, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=2, max_length=120)
    price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    data_limit_bytes: int | None = Field(default=None, gt=0)
    session_time_limit_seconds: int | None = Field(default=None, gt=0)
    validity_period_seconds: int | None = Field(default=None, gt=0)
    speed_profile: str | None = Field(default=None, max_length=100)
    description: str | None = None


class PlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    price: Decimal
    data_limit_bytes: int | None
    session_time_limit_seconds: int | None
    validity_period_seconds: int | None
    speed_profile: str | None
    description: str | None
    is_active: bool
