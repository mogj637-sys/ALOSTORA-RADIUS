from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.api.deps import get_current_owner
from app.db.session import get_db
from app.models.core import PointOfSale, PosAccountEntry
from app.schemas.reports import PosReportResponse, PosReportRow, PosReportTotals

router = APIRouter(
    prefix="/api/v1/reports",
    tags=["reports"],
    dependencies=[Depends(get_current_owner)],
)


def _money(value) -> Decimal:
    return Decimal(value or 0).quantize(Decimal("0.01"))


@router.get("/points-of-sale", response_model=PosReportResponse)
def points_of_sale_report(
    date_from: date = Query(...),
    date_to: date = Query(...),
    db: Session = Depends(get_db),
):
    if date_from > date_to:
        raise HTTPException(status_code=422, detail="تاريخ البداية يجب ألا يتجاوز تاريخ النهاية")

    start_at = datetime.combine(date_from, time.min).replace(tzinfo=timezone.utc)
    end_at = datetime.combine(date_to + timedelta(days=1), time.min).replace(tzinfo=timezone.utc)

    opening_rows = (
        db.query(
            PosAccountEntry.point_of_sale_id,
            func.coalesce(func.sum(case(
                (PosAccountEntry.direction == "debit", PosAccountEntry.amount),
                else_=-PosAccountEntry.amount,
            )), 0),
        )
        .filter(PosAccountEntry.created_at < start_at)
        .group_by(PosAccountEntry.point_of_sale_id)
        .all()
    )
    opening_by_point = {point_id: _money(balance) for point_id, balance in opening_rows}

    period_rows = (
        db.query(
            PosAccountEntry.point_of_sale_id,
            func.coalesce(func.sum(case(
                (PosAccountEntry.direction == "debit", PosAccountEntry.amount),
                else_=0,
            )), 0).label("period_debit"),
            func.coalesce(func.sum(case(
                (PosAccountEntry.direction == "credit", PosAccountEntry.amount),
                else_=0,
            )), 0).label("period_credit"),
            func.coalesce(func.sum(case(
                (PosAccountEntry.entry_type == "card_delivery", PosAccountEntry.amount),
                else_=0,
            )), 0).label("delivered_value"),
            func.coalesce(func.sum(case(
                (PosAccountEntry.entry_type == "commission", PosAccountEntry.amount),
                else_=0,
            )), 0).label("commissions"),
            func.coalesce(func.sum(case(
                (PosAccountEntry.entry_type == "payment", PosAccountEntry.amount),
                else_=0,
            )), 0).label("payments"),
            func.coalesce(func.sum(case(
                (PosAccountEntry.entry_type == "return", PosAccountEntry.amount),
                else_=0,
            )), 0).label("returns"),
            (
                func.coalesce(func.sum(case(
                    (PosAccountEntry.direction == "debit", PosAccountEntry.amount), else_=0
                )), 0)
                - func.coalesce(func.sum(case(
                    (PosAccountEntry.entry_type == "card_delivery", PosAccountEntry.amount), else_=0
                )), 0)
            ).label("other_debits"),
            (
                func.coalesce(func.sum(case(
                    (PosAccountEntry.direction == "credit", PosAccountEntry.amount), else_=0
                )), 0)
                - func.coalesce(func.sum(case(
                    (PosAccountEntry.entry_type.in_(("commission", "payment", "return")), PosAccountEntry.amount),
                    else_=0,
                )), 0)
            ).label("other_credits"),
        )
        .filter(PosAccountEntry.created_at >= start_at, PosAccountEntry.created_at < end_at)
        .group_by(PosAccountEntry.point_of_sale_id)
        .all()
    )
    period_by_point = {row[0]: row for row in period_rows}

    points = db.query(PointOfSale).order_by(PointOfSale.name.asc(), PointOfSale.id.asc()).all()
    report_rows = []
    for point in points:
        aggregate = period_by_point.get(point.id)
        opening = opening_by_point.get(point.id, Decimal("0.00"))
        if aggregate is None:
            delivered = other_debits = commissions = payments = returns = other_credits = Decimal("0.00")
            period_debit = period_credit = Decimal("0.00")
        else:
            period_debit = _money(aggregate.period_debit)
            period_credit = _money(aggregate.period_credit)
            delivered = _money(aggregate.delivered_value)
            other_debits = _money(aggregate.other_debits)
            commissions = _money(aggregate.commissions)
            payments = _money(aggregate.payments)
            returns = _money(aggregate.returns)
            other_credits = _money(aggregate.other_credits)
        report_rows.append(PosReportRow(
            point_of_sale_id=point.id,
            point_of_sale_name=point.name,
            opening_balance=opening,
            delivered_value=delivered,
            other_debits=other_debits,
            commissions=commissions,
            payments=payments,
            returns=returns,
            other_credits=other_credits,
            period_debit=period_debit,
            period_credit=period_credit,
            closing_balance=opening + period_debit - period_credit,
        ))

    def total(field: str) -> Decimal:
        return sum((getattr(row, field) for row in report_rows), Decimal("0.00"))

    totals = PosReportTotals(
        opening_balance=total("opening_balance"),
        delivered_value=total("delivered_value"),
        other_debits=total("other_debits"),
        commissions=total("commissions"),
        payments=total("payments"),
        returns=total("returns"),
        other_credits=total("other_credits"),
        period_debit=total("period_debit"),
        period_credit=total("period_credit"),
        closing_balance=total("closing_balance"),
    )
    return PosReportResponse(
        date_from=date_from,
        date_to=date_to,
        point_count=len(points),
        totals=totals,
        points=report_rows,
    )
