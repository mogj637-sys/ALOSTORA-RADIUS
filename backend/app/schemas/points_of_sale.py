from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class PointOfSaleCreate(BaseModel):
    code: str = Field(min_length=2, max_length=50, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=2, max_length=150)
    contact_name: str | None = Field(default=None, max_length=150)
    phone: str | None = Field(default=None, max_length=40)
    debt_limit: Decimal | None = Field(default=None, ge=0)
    allow_card_creation: bool = True
    allow_printing: bool = True


class PointOfSaleUpdate(BaseModel):
    name: str = Field(default=None, min_length=2, max_length=150)
    contact_name: str | None = Field(default=None, max_length=150)
    phone: str | None = Field(default=None, max_length=40)
    is_active: bool | None = None
    debt_limit: Decimal | None = Field(default=None, ge=0)
    allow_card_creation: bool | None = None
    allow_printing: bool | None = None


class PointOfSaleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    contact_name: str | None
    phone: str | None
    is_active: bool
    debt_limit: Decimal | None
    allow_card_creation: bool
    allow_printing: bool
    created_at: datetime


class PointOfSaleInventoryResponse(BaseModel):
    point_of_sale_id: int
    point_of_sale_name: str
    allocated_cards: int
    used_cards: int
    suspended_cards: int
    commercial_printed_value: Decimal
    free_cards_printed: int
