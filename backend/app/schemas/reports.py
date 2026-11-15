from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class PosReportRow(BaseModel):
    point_of_sale_id: int
    point_of_sale_name: str
    opening_balance: Decimal
    delivered_value: Decimal
    other_debits: Decimal
    commissions: Decimal
    payments: Decimal
    returns: Decimal
    other_credits: Decimal
    period_debit: Decimal
    period_credit: Decimal
    closing_balance: Decimal


class PosReportTotals(BaseModel):
    opening_balance: Decimal
    delivered_value: Decimal
    other_debits: Decimal
    commissions: Decimal
    payments: Decimal
    returns: Decimal
    other_credits: Decimal
    period_debit: Decimal
    period_credit: Decimal
    closing_balance: Decimal


class PosReportResponse(BaseModel):
    date_from: date
    date_to: date
    point_count: int
    totals: PosReportTotals
    points: list[PosReportRow]


class PosStatementEntry(BaseModel):
    id: int
    created_at: datetime
    entry_type: str
    direction: str
    amount: Decimal
    description: str | None
    reference: str | None
    created_by: str | None
    debit: Decimal
    credit: Decimal
    running_balance: Decimal


class PosStatementResponse(BaseModel):
    point_of_sale_id: int
    point_of_sale_name: str
    date_from: date
    date_to: date
    opening_balance: Decimal
    total_debit: Decimal
    total_credit: Decimal
    closing_balance: Decimal
    entries: list[PosStatementEntry]
