from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.api.deps import get_current_owner
from app.db.session import get_db
from app.models.core import PointOfSale, PosAccountEntry
from app.schemas.reports import (
    PosReportResponse, PosReportRow, PosReportTotals,
    PosStatementEntry, PosStatementResponse,
)

router = APIRouter(
    prefix="/api/v1/reports",
    tags=["reports"],
    dependencies=[Depends(get_current_owner)],
)


def _money(value) -> Decimal:
    return Decimal(value or 0).quantize(Decimal("0.01"))


def _period_bounds(date_from: date, date_to: date):
    if date_from > date_to:
        raise HTTPException(status_code=422, detail="تاريخ البداية يجب ألا يتجاوز تاريخ النهاية")
    start_at = datetime.combine(date_from, time.min).replace(tzinfo=timezone.utc)
    end_at = datetime.combine(date_to + timedelta(days=1), time.min).replace(tzinfo=timezone.utc)
    return start_at, end_at


def _report_data(date_from: date, date_to: date, db: Session) -> PosReportResponse:
    start_at, end_at = _period_bounds(date_from, date_to)
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
            func.coalesce(func.sum(case((PosAccountEntry.direction == "debit", PosAccountEntry.amount), else_=0)), 0).label("period_debit"),
            func.coalesce(func.sum(case((PosAccountEntry.direction == "credit", PosAccountEntry.amount), else_=0)), 0).label("period_credit"),
            func.coalesce(func.sum(case(((PosAccountEntry.entry_type == "card_delivery") & (PosAccountEntry.direction == "debit"), PosAccountEntry.amount), else_=0)), 0).label("delivered_value"),
            func.coalesce(func.sum(case(((PosAccountEntry.entry_type == "commission") & (PosAccountEntry.direction == "credit"), PosAccountEntry.amount), else_=0)), 0).label("commissions"),
            func.coalesce(func.sum(case(((PosAccountEntry.entry_type == "payment") & (PosAccountEntry.direction == "credit"), PosAccountEntry.amount), else_=0)), 0).label("payments"),
            func.coalesce(func.sum(case(((PosAccountEntry.entry_type == "return") & (PosAccountEntry.direction == "credit"), PosAccountEntry.amount), else_=0)), 0).label("returns"),
            func.coalesce(func.sum(case(((PosAccountEntry.direction == "debit") & (PosAccountEntry.entry_type != "card_delivery"), PosAccountEntry.amount), else_=0)), 0).label("other_debits"),
            func.coalesce(func.sum(case(((PosAccountEntry.direction == "credit") & (~PosAccountEntry.entry_type.in_(("commission", "payment", "return"))), PosAccountEntry.amount), else_=0)), 0).label("other_credits"),
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
            point_of_sale_id=point.id, point_of_sale_name=point.name,
            opening_balance=opening, delivered_value=delivered, other_debits=other_debits,
            commissions=commissions, payments=payments, returns=returns,
            other_credits=other_credits, period_debit=period_debit,
            period_credit=period_credit, closing_balance=opening + period_debit - period_credit,
        ))

    def total(field: str) -> Decimal:
        return sum((getattr(row, field) for row in report_rows), Decimal("0.00"))

    totals = PosReportTotals(
        opening_balance=total("opening_balance"), delivered_value=total("delivered_value"),
        other_debits=total("other_debits"), commissions=total("commissions"),
        payments=total("payments"), returns=total("returns"),
        other_credits=total("other_credits"), period_debit=total("period_debit"),
        period_credit=total("period_credit"), closing_balance=total("closing_balance"),
    )
    return PosReportResponse(
        date_from=date_from, date_to=date_to, point_count=len(points),
        totals=totals, points=report_rows,
    )


def _statement_data(point_id: int, date_from: date, date_to: date, db: Session) -> PosStatementResponse:
    start_at, end_at = _period_bounds(date_from, date_to)
    point = db.get(PointOfSale, point_id)
    if point is None:
        raise HTTPException(status_code=404, detail="نقطة البيع غير موجودة")
    opening_value = db.query(
        func.coalesce(func.sum(case(
            (PosAccountEntry.direction == "debit", PosAccountEntry.amount),
            else_=-PosAccountEntry.amount,
        )), 0)
    ).filter(
        PosAccountEntry.point_of_sale_id == point_id,
        PosAccountEntry.created_at < start_at,
    ).scalar()
    opening = _money(opening_value)
    records = (
        db.query(PosAccountEntry)
        .filter(
            PosAccountEntry.point_of_sale_id == point_id,
            PosAccountEntry.created_at >= start_at,
            PosAccountEntry.created_at < end_at,
        )
        .order_by(PosAccountEntry.created_at.asc(), PosAccountEntry.id.asc())
        .all()
    )
    running = opening
    entries = []
    debit_total = Decimal("0.00")
    credit_total = Decimal("0.00")
    for record in records:
        amount = _money(record.amount)
        debit = amount if record.direction == "debit" else Decimal("0.00")
        credit = amount if record.direction == "credit" else Decimal("0.00")
        debit_total += debit
        credit_total += credit
        running += debit - credit
        entries.append(PosStatementEntry(
            id=record.id, created_at=record.created_at, entry_type=record.entry_type,
            direction=record.direction, amount=amount, description=record.description,
            reference=record.reference, created_by=record.created_by,
            debit=debit, credit=credit, running_balance=running,
        ))
    return PosStatementResponse(
        point_of_sale_id=point.id, point_of_sale_name=point.name,
        date_from=date_from, date_to=date_to, opening_balance=opening,
        total_debit=debit_total, total_credit=credit_total,
        closing_balance=opening + debit_total - credit_total, entries=entries,
    )


def _workbook_response(workbook: Workbook, filename: str):
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _style_sheet(sheet):
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for cell in sheet[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="176B51")
        cell.alignment = Alignment(horizontal="center", vertical="center")
    for column in sheet.columns:
        values = [len(str(cell.value or "")) for cell in column]
        width = min(max(max(values, default=10) + 3, 14), 34)
        sheet.column_dimensions[get_column_letter(column[0].column)].width = width
    for row in sheet.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(horizontal="right", vertical="center")


@router.get("/points-of-sale", response_model=PosReportResponse)
def points_of_sale_report(
    date_from: date = Query(...), date_to: date = Query(...),
    db: Session = Depends(get_db),
):
    return _report_data(date_from, date_to, db)


@router.get("/points-of-sale/export.xlsx")
def export_points_of_sale_report(
    date_from: date = Query(...), date_to: date = Query(...),
    db: Session = Depends(get_db),
):
    report = _report_data(date_from, date_to, db)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "تقرير نقاط البيع"
    sheet.append(["نقطة البيع", "الرصيد الافتتاحي", "قيمة الكروت المسلمة", "مدين آخر", "العمولات", "السدادات", "المرتجعات", "دائن آخر", "إجمالي المدين", "إجمالي الدائن", "الرصيد الختامي"])
    for row in report.points:
        sheet.append([
            row.point_of_sale_name, float(row.opening_balance), float(row.delivered_value),
            float(row.other_debits), float(row.commissions), float(row.payments),
            float(row.returns), float(row.other_credits), float(row.period_debit),
            float(row.period_credit), float(row.closing_balance),
        ])
    sheet.append([
        "الإجمالي", float(report.totals.opening_balance), float(report.totals.delivered_value),
        float(report.totals.other_debits), float(report.totals.commissions),
        float(report.totals.payments), float(report.totals.returns),
        float(report.totals.other_credits), float(report.totals.period_debit),
        float(report.totals.period_credit), float(report.totals.closing_balance),
    ])
    _style_sheet(sheet)
    sheet.freeze_panes = "A2"
    return _workbook_response(workbook, f"pos-report-{date_from}-{date_to}.xlsx")


@router.get("/points-of-sale/{point_id}/statement", response_model=PosStatementResponse)
def point_of_sale_statement(
    point_id: int, date_from: date = Query(...), date_to: date = Query(...),
    db: Session = Depends(get_db),
):
    return _statement_data(point_id, date_from, date_to, db)


@router.get("/points-of-sale/{point_id}/statement/export.xlsx")
def export_point_of_sale_statement(
    point_id: int, date_from: date = Query(...), date_to: date = Query(...),
    db: Session = Depends(get_db),
):
    statement = _statement_data(point_id, date_from, date_to, db)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "كشف حساب نقطة البيع"
    sheet.append(["التاريخ", "نوع الحركة", "البيان", "المرجع", "المستخدم", "مدين", "دائن", "الرصيد بعد الحركة"])
    for entry in statement.entries:
        sheet.append([
            entry.created_at.replace(tzinfo=None), entry.entry_type, entry.description or "",
            entry.reference or "", entry.created_by or "", float(entry.debit),
            float(entry.credit), float(entry.running_balance),
        ])
    sheet.append(["", "", "الرصيد الافتتاحي", "", "", 0, 0, float(statement.opening_balance)])
    sheet.append(["", "", "إجمالي الفترة", "", "", float(statement.total_debit), float(statement.total_credit), float(statement.closing_balance)])
    _style_sheet(sheet)
    for row in sheet.iter_rows(min_row=2, min_col=1, max_col=1):
        if hasattr(row[0].value, "strftime"):
            row[0].number_format = "yyyy-mm-dd hh:mm"
    for row in sheet.iter_rows(min_row=2, min_col=6, max_col=8):
        for cell in row:
            cell.number_format = '#,##0.00'
    return _workbook_response(workbook, f"pos-{point_id}-statement-{date_from}-{date_to}.xlsx")
