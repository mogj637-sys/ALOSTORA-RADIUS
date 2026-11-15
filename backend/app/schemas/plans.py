from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


CommissionType = Literal["none", "fixed", "percentage"]


class PlanCreate(BaseModel):
    code: str = Field(min_length=2, max_length=50, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=2, max_length=120)
    price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    commission_type: CommissionType = "none"
    commission_value: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=12, decimal_places=2)
    data_limit_bytes: int | None = Field(default=None, gt=0)
    session_time_limit_seconds: int | None = Field(default=None, gt=0)
    validity_period_seconds: int | None = Field(default=None, gt=0)
    speed_profile: str | None = Field(default=None, max_length=100)
    description: str | None = None

    @model_validator(mode="after")
    def validate_commission(self):
        if self.commission_type == "percentage" and self.commission_value > 100:
            raise ValueError("نسبة العمولة لا يمكن أن تتجاوز 100%")
        if self.commission_type == "fixed" and self.commission_value > self.price:
            raise ValueError("العمولة الثابتة لا يمكن أن تتجاوز سعر الباقة")
        if self.commission_type == "none" and self.commission_value != 0:
            raise ValueError("قيمة العمولة يجب أن تكون صفراً عند اختيار بدون عمولة")
        return self


class PlanUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=2, max_length=50, pattern=r"^[A-Za-z0-9_-]+$")
    name: str | None = Field(default=None, min_length=2, max_length=120)
    price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    commission_type: CommissionType | None = None
    commission_value: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    data_limit_bytes: int | None = Field(default=None, gt=0)
    session_time_limit_seconds: int | None = Field(default=None, gt=0)
    validity_period_seconds: int | None = Field(default=None, gt=0)
    speed_profile: str | None = Field(default=None, max_length=100)
    description: str | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def validate_commission(self):
        if not self.model_fields_set:
            raise ValueError("يجب إرسال حقل واحد على الأقل للتعديل")
        if self.commission_type == "percentage" and self.commission_value is not None and self.commission_value > 100:
            raise ValueError("نسبة العمولة لا يمكن أن تتجاوز 100%")
        if self.commission_type == "none" and self.commission_value not in (None, Decimal("0")):
            raise ValueError("قيمة العمولة يجب أن تكون صفراً عند اختيار بدون عمولة")
        return self


class PlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    price: Decimal
    commission_type: CommissionType
    commission_value: Decimal
    data_limit_bytes: int | None
    session_time_limit_seconds: int | None
    validity_period_seconds: int | None
    speed_profile: str | None
    description: str | None
    is_active: bool
