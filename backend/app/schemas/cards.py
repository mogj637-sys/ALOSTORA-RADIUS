from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


CardType = Literal["username_only", "same_credentials", "separate_credentials"]
GenerationMode = Literal["digits", "letters", "alphanumeric"]
CardAction = Literal["suspend", "reactivate", "cancel"]


class CardSingleCreate(BaseModel):
    plan_id: int = Field(gt=0)
    username: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_-]+$")
    card_type: CardType
    password: str | None = Field(default=None, min_length=4, max_length=32)
    is_free: bool = False


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


class CardCreatedSecret(BaseModel):
    id: UUID
    serial_number: str
    username: str
    password: str


class CardCreateResponse(BaseModel):
    id: UUID
    serial_number: str
    username: str
    password: str
    card_type: str
    status: str
    is_free: bool


class CardBatchResponse(BaseModel):
    batch_id: UUID
    batch_number: str
    plan_id: int
    template_code: str | None
    point_of_sale_id: int | None
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
    created_at: datetime
    printed_count: int


class CardStatusUpdate(BaseModel):
    action: CardAction


class CardListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    serial_number: str
    username: str
    card_type: str
    status: str
    is_free: bool
    plan_id: int
    price_snapshot: Decimal
    assigned_pos_id: int | None
    first_used_at: datetime | None
    expires_at: datetime | None
