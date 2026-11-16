from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.models.core import PointOfSale, PosAccountEntry


def get_pos_balance_due(db: Session, point_id: int) -> Decimal:
    debit, credit = db.query(
        func.coalesce(
            func.sum(case((PosAccountEntry.direction == "debit", PosAccountEntry.amount), else_=0)),
            0,
        ),
        func.coalesce(
            func.sum(case((PosAccountEntry.direction == "credit", PosAccountEntry.amount), else_=0)),
            0,
        ),
    ).filter(PosAccountEntry.point_of_sale_id == point_id).one()
    return Decimal(debit or 0) - Decimal(credit or 0)


def ensure_pos_card_creation_allowed(db: Session, point: PointOfSale) -> None:
    if not point.is_active:
        raise HTTPException(status_code=409, detail="نقطة البيع متوقفة ولا يمكن إنشاء كروت لها")
    if not point.allow_card_creation:
        raise HTTPException(status_code=409, detail="الإدارة أوقفت إنشاء الكروت لهذه النقطة")
    if point.debt_limit is not None:
        balance_due = get_pos_balance_due(db, point.id)
        if balance_due >= Decimal(point.debt_limit):
            raise HTTPException(
                status_code=409,
                detail="بلغت نقطة البيع سقف المديونية؛ يجب تسجيل سداد قبل إنشاء كروت جديدة",
            )


def ensure_pos_printing_allowed(point: PointOfSale) -> None:
    if not point.is_active:
        raise HTTPException(status_code=409, detail="نقطة البيع متوقفة ولا يمكن الطباعة لها")
    if not point.allow_printing:
        raise HTTPException(status_code=409, detail="الإدارة أوقفت الطباعة لهذه النقطة")
