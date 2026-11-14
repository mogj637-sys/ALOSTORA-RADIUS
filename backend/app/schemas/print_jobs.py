from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class PrintJobCreate(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=120)
    point_of_sale_id: int = Field(gt=0)
    card_ids: list[UUID] = Field(min_length=1, max_length=5000)
    template_code: str | None = Field(default=None, max_length=80)
    is_reprint: bool = False

    @model_validator(mode="after")
    def unique_card_ids(self):
        if len(set(self.card_ids)) != len(self.card_ids):
            raise ValueError("لا يمكن تكرار الكرت داخل عملية الطباعة")
        return self


class PrintJobItemResponse(BaseModel):
    card_id: UUID
    serial_number: str
    username: str
    password: str
    is_free: bool
    price_snapshot: Decimal


class PrintJobResponse(BaseModel):
    id: UUID
    idempotency_key: str
    point_of_sale_id: int
    template_code: str | None
    card_count: int
    is_reprint: bool
    commercial_card_count: int
    free_card_count: int
    total_amount: Decimal
    items: list[PrintJobItemResponse]


class PrintJobHistoryCardResponse(BaseModel):
    card_id: UUID
    serial_number: str
    username: str
    is_free: bool


class PrintJobHistoryResponse(BaseModel):
    id: UUID
    template_code: str | None
    card_count: int
    is_reprint: bool
    created_at: datetime
    cards: list[PrintJobHistoryCardResponse]
