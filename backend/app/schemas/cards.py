from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


CardType = Literal["username_only", "same_credentials", "separate_credentials"]
GenerationMode = Literal["digits", "letters", "alphanumeric"]
CardAction = Literal["suspend", "reactivate", "cancel"]


class CardCreationPlanOption(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    price: Decimal
    data_limit_bytes: int | None
    session_time_limit_seconds: int | None
    validity_period_seconds: int | None
    speed_profile: str | None
    is_active: bool


class CardCreationTemplateOption(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    plan_id: int
    is_default: bool


class CardCreationOptionsResponse(BaseModel):
    plans: list[CardCreationPlanOption]
    templates: list[CardCreationTemplateOption]


class CardSingleCreate(BaseModel):
    plan_id: int = Field(gt=0)
    username: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_-]+$")
    card_type: CardType
    password: str | None = Field(default=None, min_length=4, max_length=32)
    is_free: bool = False
    template_code: str | None = Field(default=None, max_length=80)
    point_of_sale_id: int | None = Field(default=None, gt=0)


class CardBatchCreate(BaseModel):
    plan_id: int = Field(gt=0)
    quantity: int = Field(ge=1, le=5000)
    card_type: CardType
    generation_mode: GenerationMode = "digits"
    username_length: int = Field(default=8, ge=3, le=32)
    password_length: int = Field(default=8, ge=4, le=32)
    prefix: str = Field(default="", max_length=20, pattern=r"^[A-Za-z0-9]*$")
    template_code: str | None = Field(default=None, max_length=80)
    point_of_sale_id: int | None = Field(default=None, gt=0)
    existing_batch_id: UUID | None = None
    existing_batch_number: str | None = Field(default=None, min_length=4, max_length=40)
    is_online_sale: bool = False
    note: str | None = Field(default=None, max_length=500)


class CardCreatedSecret(BaseModel):
    id: UUID
    serial_number: str
    username: str
    password: str | None = None


class CardCreateResponse(BaseModel):
    id: UUID
    batch_id: UUID
    batch_number: str
    template_code: str | None
    point_of_sale_id: int | None
    serial_number: str
    username: str
    password: str | None = None
    card_type: str
    status: str
    is_free: bool


class CardBatchResponse(BaseModel):
    batch_id: UUID
    batch_number: str
    plan_id: int
    template_code: str | None
    point_of_sale_id: int | None
    is_online_sale: bool = False
    note: str | None = None
    created_count: int
    cards: list[CardCreatedSecret]


class CardBatchListItem(BaseModel):
    batch_id: UUID
    batch_number: str
    plan_id: int
    plan_name: str
    template_code: str | None
    point_of_sale_id: int | None
    point_of_sale_name: str | None
    quantity: int
    card_type: str
    generation_mode: str
    username_length: int
    password_length: int
    prefix: str
    created_at: datetime
    printed_count: int
    is_online_sale: bool = False
    note: str | None = None


class CardPrintSelectionResolveRequest(BaseModel):
    identifiers: list[str] = Field(min_length=1, max_length=5000)
    point_of_sale_id: int = Field(gt=0)

    @field_validator("identifiers")
    @classmethod
    def validate_identifiers(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values if value and value.strip()]
        if not cleaned:
            raise ValueError("أدخل أسماء مستخدمين أو أرقاماً تسلسلية للبحث")
        if len(cleaned) > 5000:
            raise ValueError("الحد الأقصى للاستيراد 5000 قيمة")
        return cleaned


class CardPrintSelectionItem(BaseModel):
    id: UUID
    username: str
    serial_number: str
    plan_id: int
    is_free: bool


class CardPrintSelectionResolveResponse(BaseModel):
    total_requested: int
    matched_count: int
    items: list[CardPrintSelectionItem]
    unmatched: list[str]


class CardStatusUpdate(BaseModel):
    action: CardAction
    confirmation_identifier: str | None = Field(default=None, max_length=120)


class CardDeleteOption(BaseModel):
    id: UUID
    username: str
    serial_number: str
    status: str
    first_used_at: datetime | None
    assigned_pos_id: int | None
    can_delete: bool
    blocked_reason: str | None = None


class CardListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    serial_number: str
    username: str
    card_type: str
    status: str
    is_free: bool
    plan_id: int
    batch_id: UUID | None
    price_snapshot: Decimal
    assigned_pos_id: int | None
    first_used_at: datetime | None
    expires_at: datetime | None
    used_seconds: int
    upload_bytes: int
    download_bytes: int
    plan_snapshot: dict
    total_sessions_count: int = 0
    active_sessions_count: int = 0
    ended_sessions_count: int = 0
    last_session_at: datetime | None = None
    last_session_update_at: datetime | None = None
    remaining_time_seconds: int | None = None
    remaining_data_bytes: int | None = None
    shared_users_limit: int | None = None
    speed_limit: str | None = None
