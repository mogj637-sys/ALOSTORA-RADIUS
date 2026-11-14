from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_owner
from app.db.session import get_db
from app.models.auth import AdminUser
from app.models.core import (
    Card,
    CardEvent,
    PointOfSale,
    PosInventoryMovement,
    PrintJob,
    PrintJobItem,
)
from app.services.credentials import CredentialEncryptionNotConfigured, decrypt_credential
from app.schemas.print_jobs import (
    PrintJobCreate,
    PrintJobItemResponse,
    PrintJobResponse,
)

router = APIRouter(
    prefix="/api/v1/print-jobs",
    tags=["print-jobs"],
    dependencies=[Depends(get_current_owner)],
)


def _response(job: PrintJob, db: Session) -> PrintJobResponse:
    items = (
        db.query(PrintJobItem)
        .filter(PrintJobItem.print_job_id == job.id)
        .order_by(PrintJobItem.id.asc())
        .all()
    )
    cards_by_id = {
        card.id: card
        for card in db.query(Card).filter(Card.id.in_([item.card_id for item in items])).all()
    }
    commercial = [item for item in items if not item.is_free]
    free = [item for item in items if item.is_free]
    try:
        response_items = [
            PrintJobItemResponse(
                card_id=item.card_id,
                serial_number=item.serial_number_snapshot,
                username=item.username_snapshot,
                password=decrypt_credential(cards_by_id[item.card_id].credential_ciphertext),
                is_free=item.is_free,
                price_snapshot=item.price_snapshot,
            )
            for item in items
        ]
    except CredentialEncryptionNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=500, detail="تعذر تجهيز بيانات اعتماد الطباعة") from exc

    return PrintJobResponse(
        id=job.id,
        idempotency_key=job.idempotency_key,
        point_of_sale_id=job.point_of_sale_id,
        template_code=job.template_code,
        card_count=job.card_count,
        is_reprint=job.is_reprint,
        commercial_card_count=len(commercial),
        free_card_count=len(free),
        total_amount=(
            sum((item.price_snapshot for item in commercial), Decimal("0.00"))
            if not job.is_reprint
            else Decimal("0.00")
        ),
        items=response_items,
    )

def _existing_job(
    db: Session,
    payload: PrintJobCreate,
) -> PrintJobResponse | None:
    job = (
        db.query(PrintJob)
        .filter(PrintJob.idempotency_key == payload.idempotency_key)
        .first()
    )
    if job is None:
        return None

    existing_ids = {
        item.card_id
        for item in db.query(PrintJobItem)
        .filter(PrintJobItem.print_job_id == job.id)
        .all()
    }
    if (
        job.point_of_sale_id != payload.point_of_sale_id
        or job.template_code != payload.template_code
        or job.is_reprint != payload.is_reprint
        or existing_ids != set(payload.card_ids)
    ):
        raise HTTPException(
            status_code=409,
            detail="مفتاح العملية مستخدم سابقاً لطلب طباعة مختلف",
        )
    return _response(job, db)


@router.post("", response_model=PrintJobResponse, status_code=status.HTTP_201_CREATED)
def create_print_job(
    payload: PrintJobCreate,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(get_current_owner),
):
    existing = _existing_job(db, payload)
    if existing is not None:
        return existing

    point_of_sale = db.get(PointOfSale, payload.point_of_sale_id)
    if point_of_sale is None or not point_of_sale.is_active:
        raise HTTPException(status_code=404, detail="نقطة البيع غير موجودة أو غير مفعلة")

    cards = (
        db.query(Card)
        .filter(Card.id.in_(payload.card_ids))
        .order_by(Card.id.asc())
        .with_for_update()
        .all()
    )
    if len(cards) != len(payload.card_ids):
        raise HTTPException(status_code=404, detail="بعض الكروت المطلوبة غير موجودة")

    # A concurrent retry may have committed while this request waited for card locks.
    existing = _existing_job(db, payload)
    if existing is not None:
        return existing

    if payload.is_reprint:
        original_ids = {
            row[0]
            for row in (
                db.query(PrintJobItem.card_id)
                .join(PrintJob, PrintJob.id == PrintJobItem.print_job_id)
                .filter(
                    PrintJob.point_of_sale_id == payload.point_of_sale_id,
                    PrintJob.is_reprint.is_(False),
                    PrintJobItem.card_id.in_(payload.card_ids),
                )
                .all()
            )
        }
        if original_ids != set(payload.card_ids):
            raise HTTPException(
                status_code=409,
                detail="إعادة الطباعة مسموحة للكروت التي سبق تخصيص طباعتها لهذه النقطة فقط",
            )
        for card in cards:
            if not card.is_free and card.assigned_pos_id != payload.point_of_sale_id:
                raise HTTPException(status_code=409, detail="الكرت غير مخصص لنقطة البيع المحددة")
            if card.status == "cancelled":
                raise HTTPException(status_code=409, detail="لا يمكن إعادة طباعة كرت ملغي")
    else:
        for card in cards:
            if card.status != "generated" or card.assigned_pos_id is not None:
                raise HTTPException(
                    status_code=409,
                    detail=f"الكرت {card.username} سبق تخصيصه أو لا يقبل الطباعة التجارية",
                )

    job = PrintJob(
        idempotency_key=payload.idempotency_key,
        point_of_sale_id=payload.point_of_sale_id,
        template_code=payload.template_code,
        card_count=len(cards),
        is_reprint=payload.is_reprint,
        requested_by=user.username,
    )
    db.add(job)
    try:
        db.flush()
        now = datetime.now(timezone.utc)
        for card in cards:
            db.add(
                PrintJobItem(
                    print_job_id=job.id,
                    card_id=card.id,
                    serial_number_snapshot=card.serial_number,
                    username_snapshot=card.username,
                    is_free=card.is_free,
                    price_snapshot=card.price_snapshot,
                )
            )

            if payload.is_reprint:
                event_type = "reprinted"
                details = {"print_job_id": str(job.id), "point_of_sale_id": point_of_sale.id}
            elif card.is_free:
                # Free cards remain in the technical print history but never enter POS stock.
                event_type = "printed_free"
                details = {"print_job_id": str(job.id), "commercial": False}
            else:
                card.assigned_pos_id = point_of_sale.id
                card.allocated_at = now
                card.status = "allocated"
                db.add(
                    PosInventoryMovement(
                        point_of_sale_id=point_of_sale.id,
                        card_id=card.id,
                        print_job_id=job.id,
                        movement_type="allocation",
                        quantity=1,
                        amount=card.price_snapshot,
                        idempotency_key=f"print-job:{job.id}:{card.id}",
                    )
                )
                event_type = "printed_to_pos"
                details = {
                    "print_job_id": str(job.id),
                    "point_of_sale_id": point_of_sale.id,
                    "amount": str(card.price_snapshot),
                }

            db.add(
                CardEvent(
                    card_id=card.id,
                    event_type=event_type,
                    details=details,
                    actor=user.username,
                )
            )

        db.commit()
        db.refresh(job)
    except IntegrityError:
        db.rollback()
        existing = _existing_job(db, payload)
        if existing is not None:
            return existing
        raise HTTPException(status_code=409, detail="تعذر تسجيل عملية الطباعة بسبب تعارض؛ لم يتم ترحيل المخزون")

    return _response(job, db)
