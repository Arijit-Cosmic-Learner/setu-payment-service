"""
event_service.py
----------------
Business logic for event ingestion.

This is the most important file for the interview because it contains:
1. IDEMPOTENCY: handles duplicate events gracefully
2. STATE MACHINE: enforces valid payment status transitions
3. UPSERT LOGIC: creates merchants and transactions if they don't exist

WHY in a service file and not directly in the router?
- Separation of concerns: routers handle HTTP, services handle business logic
- Easier to test: we can test this without making HTTP requests
- Reusable: another part of the app could call this same logic
"""

from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app import models
from app.schemas import EventCreate


# ===========================================================
# PAYMENT STATUS STATE MACHINE
# ===========================================================
# Defines which status the transaction should move to
# when each event type is received.
#
# KEY INSIGHT: 'settled' only changes settlement_status, NOT payment_status.
# This is intentional — it lets us detect discrepancies like:
#   payment_status=failed + settlement_status=settled (impossible, needs investigation)

EVENT_TO_PAYMENT_STATUS = {
    "payment_initiated": "initiated",
    "payment_processed": "processed",
    "payment_failed":    "failed",
    "settled":           None,   # settled event does NOT change payment_status
}

EVENT_TO_SETTLEMENT_STATUS = {
    "payment_initiated": "pending",
    "payment_processed": "pending",
    "payment_failed":    "pending",
    "settled":           "settled",
}

EVENT_TO_STATUS = {
    "payment_initiated": "initiated",
    "payment_processed": "processed",
    "payment_failed":    "failed",
    "settled":           "settled",
}


def upsert_merchant(db: Session, merchant_id: str, merchant_name: str) -> models.Merchant:
    """
    Get existing merchant or create a new one.
    'Upsert' = Update if exists, Insert if not.
    """
    merchant = db.query(models.Merchant).filter(
        models.Merchant.merchant_id == merchant_id
    ).first()

    if not merchant:
        merchant = models.Merchant(
            merchant_id=merchant_id,
            merchant_name=merchant_name,
        )
        db.add(merchant)
        db.flush()  # flush sends SQL to DB but does NOT commit yet

    return merchant


def upsert_transaction(db: Session, event: EventCreate) -> models.Transaction:
    """
    Get existing transaction or create a new one.
    Then update its status based on the incoming event type.
    """
    transaction = db.query(models.Transaction).filter(
        models.Transaction.transaction_id == event.transaction_id
    ).first()

    new_payment_status = EVENT_TO_PAYMENT_STATUS.get(event.event_type)
    new_settlement_status = EVENT_TO_SETTLEMENT_STATUS.get(event.event_type, "pending")
    new_status = EVENT_TO_STATUS.get(event.event_type, "initiated")

    if not transaction:
        # First event for this transaction — create it
        transaction = models.Transaction(
            transaction_id=event.transaction_id,
            merchant_id=event.merchant_id,
            amount=event.amount,
            currency=event.currency,
            payment_status=new_payment_status or "initiated",
            settlement_status=new_settlement_status,
            status=new_status,
        )
        db.add(transaction)
        db.flush()
    else:
        # Transaction exists — update its status
        # Only update payment_status if the event type affects it
        if new_payment_status is not None:
            transaction.payment_status = new_payment_status
        transaction.settlement_status = new_settlement_status
        transaction.status = new_status
        transaction.updated_at = datetime.now(timezone.utc)

    return transaction


def ingest_event(db: Session, event: EventCreate) -> dict:
    """
    Main entry point for event ingestion.

    IDEMPOTENCY FLOW:
    1. Check if event_id already exists in payment_events
    2. If YES  → return the existing event with status 'already_processed'
                  (no DB changes, no error — this is the correct behavior)
    3. If NO   → process the event:
                  a. Upsert merchant
                  b. Upsert/update transaction
                  c. Insert new payment_event record
                  d. Commit everything

    This function NEVER raises an error for duplicates.
    The UNIQUE constraint on event_id is our safety net if this check somehow fails.
    """

    # ---------------------------------------------------
    # STEP 1: Idempotency Check
    # ---------------------------------------------------
    existing_event = db.query(models.PaymentEvent).filter(
        models.PaymentEvent.event_id == event.event_id
    ).first()

    if existing_event:
        # Duplicate detected — return safely without any changes
        return {
            "event_id": existing_event.event_id,
            "event_type": existing_event.event_type,
            "transaction_id": existing_event.transaction_id,
            "merchant_id": existing_event.merchant_id,
            "amount": existing_event.amount,
            "currency": existing_event.currency,
            "timestamp": existing_event.timestamp,
            "received_at": existing_event.received_at,
            "ingestion_status": "already_processed",
        }

    # ---------------------------------------------------
    # STEP 2: Process the new event
    # ---------------------------------------------------
    try:
        # 2a. Ensure merchant exists
        upsert_merchant(db, event.merchant_id, event.merchant_name)

        # 2b. Ensure transaction exists and update its status
        upsert_transaction(db, event)

        # 2c. Record the event in payment_events
        payment_event = models.PaymentEvent(
            event_id=event.event_id,
            event_type=event.event_type,
            transaction_id=event.transaction_id,
            merchant_id=event.merchant_id,
            amount=event.amount,
            currency=event.currency,
            timestamp=event.timestamp,
        )
        db.add(payment_event)

        # 2d. Commit all changes atomically
        # If ANY step fails, ALL changes are rolled back (ACID transaction)
        db.commit()
        db.refresh(payment_event)

        return {
            "event_id": payment_event.event_id,
            "event_type": payment_event.event_type,
            "transaction_id": payment_event.transaction_id,
            "merchant_id": payment_event.merchant_id,
            "amount": payment_event.amount,
            "currency": payment_event.currency,
            "timestamp": payment_event.timestamp,
            "received_at": payment_event.received_at,
            "ingestion_status": "created",
        }

    except IntegrityError:
        # The UNIQUE constraint on event_id fired — a race condition duplicate
        # This is our second line of defense after the explicit check above
        db.rollback()
        existing_event = db.query(models.PaymentEvent).filter(
            models.PaymentEvent.event_id == event.event_id
        ).first()
        return {
            "event_id": existing_event.event_id,
            "event_type": existing_event.event_type,
            "transaction_id": existing_event.transaction_id,
            "merchant_id": existing_event.merchant_id,
            "amount": existing_event.amount,
            "currency": existing_event.currency,
            "timestamp": existing_event.timestamp,
            "received_at": existing_event.received_at,
            "ingestion_status": "already_processed",
        }
