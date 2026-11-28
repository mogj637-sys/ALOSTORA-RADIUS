from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PosAccountEntryCreate(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=120)
    entry_type: Literal["payment", "commission", "return", "adjustment"]
    direction: Literal["debit", "credit"]
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    description: str | None = Field(default=None, max_length=500)
    reference: str | None = Field(default=None, max_length=120)


class PosAccountEntryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str | None = Field(default=None, max_length=500)
    reference: str | None = Field(default=None, max_length=120)


class PosAccountEntryReverse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: str = Field(min_length=8, max_length=120)
    reason: str | None = Field(default=None, max_length=400)


class PosAccountEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    point_of_sale_id: int
    entry_type: str
    direction: str
    amount: Decimal
    description: str | None
    reference: str | None
    idempotency_key: str
    created_by: str | None
    created_at: datetime
    reversal_of_id: int | None = None
    reversed_by_id: int | None = None


class PosAccountEntryOperationOption(BaseModel):
    id: int
    point_of_sale_id: int
    entry_type: str
    direction: str
    amount: Decimal
    description: str | None
    reference: str | None
    created_at: datetime
    reversal_of_id: int | None = None
    reversed_by_id: int | None = None


class PosAccountSummaryResponse(BaseModel):
    point_of_sale_id: int
    point_of_sale_name: str
    total_debit: Decimal
    total_credit: Decimal
    balance_due: Decimal
