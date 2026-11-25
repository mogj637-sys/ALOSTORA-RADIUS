from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_permission
from app.db.session import get_db
from app.models.auth import AdminUser
from app.models.core import (
    Card,
    CardBatch,
    CardEvent,
    PointOfSale,
    Plan,
    PosInventoryMovement,
    PosAccountEntry,
    PrintJob,
    PrintJobItem,
)
from app.services.credentials import CredentialEncryptionNotConfigured, decrypt_credential
from app.services.audit import record_audit
from app.services.permissions import card_visibility, has_permission
from app.services.pos_credit import ensure_pos_printing_allowed, get_pos_balance_due
from app.schemas.print_jobs import (
    PrintJobCreate,
    PrintJobHistoryCardResponse,
    PrintJobHistoryResponse,
    PrintJobItemResponse,
    PrintJobResponse,
)

router = APIRouter(
    prefix="/api/v1/print-jobs",
    tags=["print-jobs"],
)


def _response(job: PrintJob, db: Session, include_credentials: bool) -> PrintJobResponse:
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
    plans_by_id = {plan.id: plan for plan in db.query(Plan).filter(Plan.id.in_({card.plan_id for card in cards_by_id.values()})).all()}
    try:
        response_items = [
            PrintJobItemResponse(
                card_id=item.card_id,
                serial_number=item.serial_number_snapshot,
                username=item.username_snapshot,
                password=decrypt_credential(cards_by_id[item.card_id].credential_ciphertext) if include_credentials else None,
                is_free=item.is_free,
                price_snapshot=item.price_snapshot,
                plan_name=plans_by_id[cards_by_id[item.card_id].plan_id].name,
                data_limit_bytes=plans_by_id[cards_by_id[item.card_id].plan_id].data_limit_bytes,
                session_time_limit_seconds=plans_by_id[cards_by_id[item.card_id].plan_id].session_time_limit_seconds,
                validity_period_seconds=plans_by_id[cards_by_id[item.card_id].plan_id].validity_period_seconds,
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
        print_options=job.print_options or {},
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
    include_credentials: bool,
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
        or (job.print_options or {}) != payload.print_options.model_dump()
        or existing_ids != set(payload.card_ids)
    ):
        raise HTTPException(
            status_code=409,
            detail="مفتاح العملية مستخدم سابقاً لطلب طباعة مختلف",
        )
    return _response(job, db, include_credentials)


@router.get("", response_model=list[PrintJobHistoryResponse], dependencies=[Depends(require_permission("printing.view"))])
def list_print_jobs(
    point_of_sale_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_permission("printing.view")),
):
    is_system_owner = any(role.code == "owner" for role in user.roles)
    assigned_point_ids = {point.id for point in user.point_of_sales}

    query = db.query(PrintJob)
    if point_of_sale_id is not None:
        if not is_system_owner and point_of_sale_id not in assigned_point_ids:
            raise HTTPException(status_code=403, detail="لا تملك صلاحية الاطلاع على عمليات نقطة البيع هذه")
        point = db.get(PointOfSale, point_of_sale_id)
        if point is None:
            raise HTTPException(status_code=404, detail="نقطة البيع غير موجودة")
        query = query.filter(PrintJob.point_of_sale_id == point_of_sale_id)
    elif not is_system_owner:
        if not assigned_point_ids:
            return []
        query = query.filter(PrintJob.point_of_sale_id.in_(assigned_point_ids))

    jobs = (
        query
        .order_by(PrintJob.created_at.desc())
        .limit(limit)
        .all()
    )
    point_ids = {job.point_of_sale_id for job in jobs}
    point_names = {
        point.id: point.name
        for point in db.query(PointOfSale).filter(PointOfSale.id.in_(point_ids)).all()
    } if point_ids else {}

    return [
        PrintJobHistoryResponse(
            id=job.id,
            point_of_sale_id=job.point_of_sale_id,
            point_of_sale_name=point_names.get(job.point_of_sale_id, "نقطة بيع غير متاحة"),
            template_code=job.template_code,
            print_options=job.print_options or {},
            card_count=job.card_count,
            is_reprint=job.is_reprint,
            created_at=job.created_at,
            cards=[
                PrintJobHistoryCardResponse(
                    card_id=item.card_id,
                    serial_number=item.serial_number_snapshot,
                    username=item.username_snapshot,
                    is_free=item.is_free,
                )
                for item in job.items
            ],
        )
        for job in jobs
    ]


def require_print_job_permission(payload: PrintJobCreate, user: AdminUser = Depends(get_current_user)) -> AdminUser:
    required_action = "printing.reprint" if payload.is_reprint else "printing.create"
    if not has_permission(user, required_action):
        message = "ليست لديك صلاحية إعادة الطباعة" if payload.is_reprint else "ليست لديك صلاحية تنفيذ الطباعة"
        raise HTTPException(status_code=403, detail=message)
    if not has_permission(user, "printing.credentials"):
        raise HTTPException(status_code=403, detail="تتطلب الطباعة صلاحية مستقلة لعرض بيانات دخول الكروت")
    return user


@router.post("", response_model=PrintJobResponse, status_code=status.HTTP_201_CREATED)
def create_print_job(
    payload: PrintJobCreate,
    response: Response,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_print_job_permission),
):
    # Voucher credentials are returned only to accounts explicitly granted credential access.
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
    response.headers["Pragma"] = "no-cache"
    if not any(role.code == "owner" for role in user.roles) and payload.point_of_sale_id not in {point.id for point in user.point_of_sales}:
        raise HTTPException(status_code=403, detail="لا تملك صلاحية الطباعة لنقطة البيع هذه")
    point_of_sale = (
        db.query(PointOfSale)
        .filter(PointOfSale.id == payload.point_of_sale_id)
        .with_for_update()
        .first()
    )
    if point_of_sale is None:
        raise HTTPException(status_code=404, detail="نقطة البيع غير موجودة")
    cards = (
        db.query(Card)
        .filter(Card.id.in_(payload.card_ids))
        .order_by(Card.id.asc())
        .with_for_update()
        .all()
    )
    if len(cards) != len(payload.card_ids):
        raise HTTPException(status_code=404, detail="بعض الكروت المطلوبة غير موجودة")

    batch_ids = {card.batch_id for card in cards if card.batch_id is not None}
    if batch_ids:
        batches = db.query(CardBatch).filter(CardBatch.id.in_(batch_ids)).all()
        for batch in batches:
            if batch.point_of_sale_id is not None and batch.point_of_sale_id != payload.point_of_sale_id:
                raise HTTPException(status_code=409, detail=f"الدفعة {batch.batch_number} مخصصة لنقطة بيع أخرى")
            if batch.template_code and batch.template_code != payload.template_code:
                raise HTTPException(status_code=409, detail=f"يجب استخدام قالب الدفعة {batch.template_code}")

    if card_visibility(user) == "assigned":
        allowed_batch_ids = {
            row[0]
            for row in db.query(CardBatch.id)
            .filter(CardBatch.point_of_sale_id == point_of_sale.id)
            .all()
        }
        if any(card.batch_id is None or card.batch_id not in allowed_batch_ids for card in cards):
            raise HTTPException(status_code=403, detail="لا تملك صلاحية طباعة كروت خارج نطاق نقاط البيع المرتبطة بحسابك")
    else:
        allowed_batch_ids = {
            row[0]
            for row in db.query(CardBatch.id)
            .filter(
                or_(
                    CardBatch.point_of_sale_id == point_of_sale.id,
                    CardBatch.point_of_sale_id.is_(None),
                )
            )
            .all()
        }
        if any(card.batch_id is not None and card.batch_id not in allowed_batch_ids for card in cards):
            raise HTTPException(status_code=403, detail="لا تملك صلاحية طباعة كروت مخصصة لنقطة بيع أخرى")

    existing = _existing_job(db, payload, include_credentials=True)
    if existing is not None:
        return existing

    ensure_pos_printing_allowed(point_of_sale)

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

    commercial_cards = [card for card in cards if not card.is_free] if not payload.is_reprint else []
    commercial_total = sum(
        (card.price_snapshot for card in commercial_cards),
        Decimal("0.00"),
    )
    commission_by_plan: dict[int, Decimal] = {}
    plans_by_id: dict[int, Plan] = {}
    if commercial_cards:
        plan_ids = {card.plan_id for card in commercial_cards}
        plans_by_id = {
            plan.id: plan
            for plan in db.query(Plan).filter(Plan.id.in_(plan_ids)).all()
        }
        for card in commercial_cards:
            plan = plans_by_id.get(card.plan_id)
            if plan is None or plan.commission_type == "none":
                continue
            if plan.commission_type == "percentage":
                commission = (
                    card.price_snapshot * plan.commission_value / Decimal("100")
                ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            elif plan.commission_type == "fixed":
                commission = min(plan.commission_value, card.price_snapshot)
            else:
                continue
            if commission > 0:
                commission_by_plan[plan.id] = (
                    commission_by_plan.get(plan.id, Decimal("0.00")) + commission
                )

    commission_total = sum(commission_by_plan.values(), Decimal("0.00"))
    if point_of_sale.debt_limit is not None:
        current_due = get_pos_balance_due(db, point_of_sale.id)
        debt_limit = Decimal(point_of_sale.debt_limit)
        if current_due >= debt_limit:
            raise HTTPException(
                status_code=409,
                detail="بلغت نقطة البيع سقف المديونية؛ يجب تسجيل سداد قبل تنفيذ عمليات طباعة جديدة",
            )
        if not payload.is_reprint:
            projected_due = current_due + commercial_total - commission_total
            if projected_due > debt_limit:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "ستتجاوز هذه العملية سقف المديونية لنقطة البيع. "
                        f"الرصيد الحالي {current_due:.2f} ريال، "
                        f"والسقف {debt_limit:.2f} ريال"
                    ),
                )

    job = PrintJob(
        idempotency_key=payload.idempotency_key,
        point_of_sale_id=payload.point_of_sale_id,
        template_code=payload.template_code,
        print_options=payload.print_options.model_dump(),
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
                # Free cards are marked as printed to prevent a second original allocation.
                card.status = "printed_free"
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

        # Original commercial allocation creates a debit for delivered cards
        # and a credit for configured commissions. Free cards and reprints are excluded.
        if not payload.is_reprint:
            if commercial_total > 0:
                db.add(
                    PosAccountEntry(
                        point_of_sale_id=point_of_sale.id,
                        entry_type="card_delivery",
                        direction="debit",
                        amount=commercial_total,
                        description=f"تسليم كروت عبر عملية الطباعة {job.id}",
                        reference=str(job.id),
                        idempotency_key=f"print-job-account:{job.id}",
                        created_by=user.username,
                    )
                )

            for plan_id, commission_total in commission_by_plan.items():
                db.add(
                    PosAccountEntry(
                        point_of_sale_id=point_of_sale.id,
                        entry_type="commission",
                        direction="credit",
                        amount=commission_total,
                        description=f"عمولة تسليم باقة {plans_by_id[plan_id].name} عبر الطباعة {job.id}",
                        reference=str(job.id),
                        idempotency_key=f"print-job-commission:{job.id}:{plan_id}",
                        created_by=user.username,
                    )
                )

        record_audit(db, user, "print.reprint_created" if payload.is_reprint else "print.job_created", "print_job", f"{"إعادة طباعة" if payload.is_reprint else "طباعة"} {len(cards)} كرت لنقطة البيع {point_of_sale.name}", entity_id=job.id, details={"card_count": len(cards), "point_of_sale_id": point_of_sale.id, "template_code": payload.template_code, "is_reprint": payload.is_reprint})
        db.commit()
        db.refresh(job)
    except IntegrityError:
        db.rollback()
        existing = _existing_job(db, payload, include_credentials=True)
        if existing is not None:
            return existing
        raise HTTPException(status_code=409, detail="تعذر تسجيل عملية الطباعة بسبب تعارض؛ لم يتم ترحيل المخزون")

    return _response(job, db, include_credentials=True)
