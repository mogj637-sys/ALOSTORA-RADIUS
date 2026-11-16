from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class PrintOptions(BaseModel):
    show_username: bool = True
    show_password: bool = True
    show_serial_number: bool = True
    show_plan: bool = True
    show_price: bool = True
    show_limits: bool = True
    sequential: bool = False


class PrintJobCreate(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=120)
    point_of_sale_id: int = Field(gt=0)
    card_ids: list[UUID] = Field(min_length=1, max_length=5000)
    template_code: str | None = Field(default=None, max_length=80)
    is_reprint: bool = False
    print_options: PrintOptions = Field(default_factory=PrintOptions)

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
    print_options: dict
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
    print_options: dict
    created_at: datetime
    cards: list[PrintJobHistoryCardResponse]
