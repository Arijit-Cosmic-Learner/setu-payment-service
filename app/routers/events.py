"""
routers/events.py
-----------------
Handles POST /events — the event ingestion endpoint.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import EventCreate, EventResponse
from app.services.event_service import ingest_event

router = APIRouter(prefix="/events", tags=["Events"])


@router.post(
    "",
    response_model=EventResponse,
    status_code=status.HTTP_200_OK,
    summary="Ingest a payment lifecycle event",
    description="""
    Accepts payment lifecycle events and stores them idempotently.

    **Idempotency**: Sending the same event_id multiple times is safe.
    The second (and subsequent) calls return the original result with
    `ingestion_status: already_processed` — no duplicate records are created.

    **Supported event types:**
    - `payment_initiated` — a new payment has started
    - `payment_processed` — the payment was successful
    - `payment_failed`    — the payment failed
    - `settled`           — funds have been credited to the merchant
    """,
)
def ingest_payment_event(
    event: EventCreate,
    db: Session = Depends(get_db),
):
    """
    POST /events

    FastAPI automatically:
    - Parses the JSON body into EventCreate (Pydantic validates it)
    - Injects the DB session via Depends(get_db)
    - Validates the response against EventResponse before sending

    We always return 200 OK (not 201) because:
    - If it's a new event: 200 OK with ingestion_status='created'
    - If it's a duplicate: 200 OK with ingestion_status='already_processed'
    Returning 409 for duplicates would break partner retry logic.
    """
    result = ingest_event(db=db, event=event)
    return result
