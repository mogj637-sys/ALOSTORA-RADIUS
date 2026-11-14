from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class PrintJobCreate(BaseModel):
    idempotency_key: str
    point_of_sale_id: int
    card_ids: list[UUID]
    template_code: str | None = None
    is_reprint: bool = False


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
