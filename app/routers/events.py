"""
routers/events.py
-----------------
POST /events - ingest a payment lifecycle event (idempotent)
GET  /events - list events with pagination and filtering
"""

import math
from typing import Optional, Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc

from app import models
from app.database import get_db
from app.config import settings
from app.schemas import EventCreate, EventResponse, EventSummary, PaginatedEvents
from app.services.event_service import ingest_event

router = APIRouter(prefix="/events", tags=["Events"])


# ===========================================================
# POST /events - Ingest a payment lifecycle event
# ===========================================================
@router.post(
    "",
    response_model=EventResponse,
    status_code=status.HTTP_200_OK,
    summary="Ingest a payment lifecycle event",
    description="""
    Accepts payment lifecycle events and stores them idempotently.

    **Idempotency**: Sending the same event_id multiple times is safe.
    The second (and subsequent) calls return the original result with
    `ingestion_status: already_processed` - no duplicate records are created.

    **Supported event types:**
    - `payment_initiated` - a new payment has started
    - `payment_processed` - the payment was successful
    - `payment_failed`    - the payment failed
    - `settled`           - funds have been credited to the merchant
    """,
)
def ingest_payment_event(
    event: EventCreate,
    db: Session = Depends(get_db),
):
    result = ingest_event(db=db, event=event)
    return result


# ===========================================================
# GET /events - List events with pagination and filtering
# ===========================================================
@router.get(
    "",
    response_model=PaginatedEvents,
    summary="List payment events with pagination and filtering",
    description="""
    Returns a paginated list of payment events, ordered by timestamp descending.

    **Filters:**
    - `transaction_id` - narrow to events for one transaction
    - `merchant_id`    - narrow to events for one merchant
    - `event_type`     - filter by event type (payment_initiated, payment_processed, etc.)
    """,
)
def list_events(
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(default=None, description="Items per page"),
    transaction_id: Optional[str] = Query(default=None, description="Filter by transaction ID"),
    merchant_id: Optional[str] = Query(default=None, description="Filter by merchant ID"),
    event_type: Optional[Literal[
        "payment_initiated", "payment_processed", "payment_failed", "settled"
    ]] = Query(default=None, description="Filter by event type"),
    sort_order: Literal["asc", "desc"] = Query(default="desc", description="Sort by timestamp"),
    db: Session = Depends(get_db),
):
    if page_size is None:
        page_size = settings.DEFAULT_PAGE_SIZE
    page_size = min(page_size, settings.MAX_PAGE_SIZE)

    query = db.query(models.PaymentEvent)

    if transaction_id:
        query = query.filter(models.PaymentEvent.transaction_id == transaction_id)
    if merchant_id:
        query = query.filter(models.PaymentEvent.merchant_id == merchant_id)
    if event_type:
        query = query.filter(models.PaymentEvent.event_type == event_type)

    total = query.count()

    if sort_order == "desc":
        query = query.order_by(desc(models.PaymentEvent.timestamp))
    else:
        query = query.order_by(asc(models.PaymentEvent.timestamp))

    offset = (page - 1) * page_size
    events = query.offset(offset).limit(page_size).all()

    items = [
        EventSummary(
            event_id=e.event_id,
            event_type=e.event_type,
            transaction_id=e.transaction_id,
            merchant_id=e.merchant_id,
            amount=e.amount,
            currency=e.currency,
            timestamp=e.timestamp,
            received_at=e.received_at,
        )
        for e in events
    ]

    return PaginatedEvents(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total > 0 else 0,
        items=items,
    )
