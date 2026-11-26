from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


CommissionType = Literal["none", "fixed", "percentage"]


def _validate_plan_settings(settings: dict | None) -> None:
    if settings is None:
        return
    shared_users = settings.get("shared_users")
    if shared_users not in (None, ""):
        try:
            numeric_shared_users = Decimal(str(shared_users))
        except Exception as exc:
            raise ValueError("عدد المستخدمين المتزامنين يجب أن يكون عدداً صحيحاً موجباً") from exc
        if numeric_shared_users < 1 or numeric_shared_users != numeric_shared_users.to_integral_value():
            raise ValueError("عدد المستخدمين المتزامنين يجب أن يكون عدداً صحيحاً موجباً")

    rx = settings.get("rate_limit_rx")
    tx = settings.get("rate_limit_tx")
    if (rx in (None, "")) != (tx in (None, "")):
        raise ValueError("يجب تحديد سرعتي التنزيل والرفع معاً")
    if rx not in (None, ""):
        try:
            if Decimal(str(rx)) <= 0 or Decimal(str(tx)) <= 0:
                raise ValueError("قيم السرعة يجب أن تكون أكبر من صفر")
        except Exception as exc:
            raise ValueError("قيم السرعة يجب أن تكون أرقاماً موجبة") from exc
        if settings.get("rate_limit_unit", "Kbps") not in {"Kbps", "Mbps"}:
            raise ValueError("وحدة السرعة غير مدعومة")

    schedule = settings.get("schedule") or {}
    if schedule.get("enabled"):
        days = schedule.get("days")
        if not isinstance(days, list) or not days or any(str(day) not in {"0", "1", "2", "3", "4", "5", "6"} for day in days):
            raise ValueError("اختر يوماً واحداً على الأقل لجدولة الباقة")
        for key in ("from", "to"):
            value = schedule.get(key)
            if not isinstance(value, str) or len(value) != 5 or value[2] != ":":
                raise ValueError("وقت الجدولة يجب أن يكون بصيغة HH:MM")
            try:
                hour, minute = (int(part) for part in value.split(":"))
            except ValueError as exc:
                raise ValueError("وقت الجدولة يجب أن يكون بصيغة HH:MM") from exc
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError("وقت الجدولة غير صحيح")

    notifications = settings.get("notifications") or {}
    for key in ("remaining_percent", "exhausted_percent"):
        value = notifications.get(key)
        if value is not None and not 1 <= int(value) <= 100:
            raise ValueError("نسب التنبيهات يجب أن تكون بين 1 و100")


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
    settings: dict = Field(default_factory=dict)
    description: str | None = None

    @model_validator(mode="after")
    def validate_commission(self):
        _validate_plan_settings(self.settings)
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
    commission_type: CommissionType = "none"
    commission_value: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=12, decimal_places=2)
    data_limit_bytes: int | None = Field(default=None, gt=0)
    session_time_limit_seconds: int | None = Field(default=None, gt=0)
    validity_period_seconds: int | None = Field(default=None, gt=0)
    speed_profile: str | None = Field(default=None, max_length=100)
    settings: dict | None = None
    description: str | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def validate_commission(self):
        if "settings" in self.model_fields_set:
            _validate_plan_settings(self.settings)
        if not self.model_fields_set:
            raise ValueError("يجب إرسال حقل واحد على الأقل للتعديل")
        if "commission_type" in self.model_fields_set and self.commission_type == "percentage" and self.commission_value > 100:
            raise ValueError("نسبة العمولة لا يمكن أن تتجاوز 100%")
        if "commission_type" in self.model_fields_set and self.commission_type == "none" and "commission_value" in self.model_fields_set and self.commission_value != 0:
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
    settings: dict
    description: str | None
    is_active: bool

class PlanOperationOption(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    is_active: bool

