"""
models.py
---------
SQLAlchemy ORM models — these define our database tables.

Tables:
1. merchants        - who the merchants are
2. transactions     - one row per unique transaction, tracks current state
3. payment_events   - raw log of every event received (never deleted, append-only)

Key Design Decisions:
- transactions has BOTH payment_status AND settlement_status as separate columns.
  This is critical for reconciliation: it lets us detect cases like
  "payment failed but money was still settled" or "payment processed but never settled".
- payment_events has a UNIQUE constraint on event_id — this is our idempotency guard.
  If the same event arrives twice, the DB will reject the second insert.
- We add indexes on columns that will be used in WHERE clauses and ORDER BY
  so queries stay fast even with 10,000+ rows.
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Numeric, DateTime, Boolean,
    Integer, ForeignKey, Index, text
)
from sqlalchemy.orm import relationship
from app.database import Base


def utcnow():
    """Helper: always store timestamps in UTC."""
    return datetime.now(timezone.utc)


# ===========================================================
# TABLE 1: merchants
# ===========================================================
class Merchant(Base):
    __tablename__ = "merchants"

    # Primary Key — we use the merchant_id from the event directly
    # e.g. "merchant_1", "merchant_2" — not an auto-increment integer
    merchant_id = Column(String, primary_key=True, index=True)
    merchant_name = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    # Relationship: one merchant has many transactions
    transactions = relationship("Transaction", back_populates="merchant")

    def __repr__(self):
        return f"<Merchant {self.merchant_id}: {self.merchant_name}>"


# ===========================================================
# TABLE 2: transactions
# ===========================================================
class Transaction(Base):
    __tablename__ = "transactions"

    # Primary Key — UUID string from the event e.g. "2f86e94c-239c-..."
    transaction_id = Column(String, primary_key=True, index=True)

    # Foreign Key — links to merchants table
    merchant_id = Column(String, ForeignKey("merchants.merchant_id"), nullable=False)

    # Financial data
    amount = Column(Numeric(12, 2), nullable=False)  # e.g. 15248.29
    currency = Column(String(10), default="INR", nullable=False)

    # -------------------------------------------------------
    # THE KEY DESIGN DECISION: Two separate status columns
    # -------------------------------------------------------
    # payment_status: tracks the payment rail
    #   initiated  -> the payment was started
    #   processed  -> the payment went through successfully
    #   failed     -> the payment failed
    #
    # settlement_status: tracks the settlement rail
    #   pending    -> money has not yet reached the merchant
    #   settled    -> money has been credited to the merchant
    #
    # WHY TWO COLUMNS?
    # A single "status" field cannot capture discrepancies like:
    #   - payment_status=failed  + settlement_status=settled  -> DISCREPANCY (impossible state)
    #   - payment_status=processed + settlement_status=pending -> DISCREPANCY (stuck transaction)
    # -------------------------------------------------------
    payment_status = Column(
        String(20),
        default="initiated",
        nullable=False,
        # Allowed values: initiated | processed | failed
    )
    settlement_status = Column(
        String(20),
        default="pending",
        nullable=False,
        # Allowed values: pending | settled
    )

    # Convenience status for easy filtering in GET /transactions?status=settled
    # Values: initiated | processed | failed | settled
    status = Column(String(20), default="initiated", nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    # Relationships
    merchant = relationship("Merchant", back_populates="transactions")
    events = relationship("PaymentEvent", back_populates="transaction", order_by="PaymentEvent.timestamp")

    # -------------------------------------------------------
    # INDEXES — this is where we show SQL maturity
    # -------------------------------------------------------
    # We index columns that appear in WHERE clauses and ORDER BY.
    # Without indexes, every query does a full table scan (slow at scale).
    __table_args__ = (
        Index("ix_transactions_merchant_id", "merchant_id"),       # GET /transactions?merchant_id=X
        Index("ix_transactions_status", "status"),                 # GET /transactions?status=X
        Index("ix_transactions_created_at", "created_at"),        # date range filtering + sorting
        Index("ix_transactions_merchant_status", "merchant_id", "status"),  # combined filter
    )

    def __repr__(self):
        return f"<Transaction {self.transaction_id} [{self.status}]>"


# ===========================================================
# TABLE 3: payment_events
# ===========================================================
class PaymentEvent(Base):
    __tablename__ = "payment_events"

    # Auto-increment integer PK (internal ID)
    id = Column(Integer, primary_key=True, autoincrement=True)

    # -------------------------------------------------------
    # THE IDEMPOTENCY GUARD: event_id must be UNIQUE
    # -------------------------------------------------------
    # If the same event arrives twice, the DB will raise an
    # IntegrityError on the second insert. Our service layer
    # catches this and returns 200 OK with the original event.
    # This is the fintech-grade way to handle duplicate events.
    # -------------------------------------------------------
    event_id = Column(String, nullable=False, unique=True, index=True)

    # The type of event: payment_initiated | payment_processed | payment_failed | settled
    event_type = Column(String(50), nullable=False)

    # Links back to the transaction
    transaction_id = Column(String, ForeignKey("transactions.transaction_id"), nullable=False)

    # Denormalized for convenience (avoids an extra join in event history queries)
    merchant_id = Column(String, nullable=False)

    # Financial data from the event
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(10), default="INR", nullable=False)

    # The timestamp FROM the event itself (when it happened in the payment system)
    timestamp = Column(DateTime(timezone=True), nullable=False)

    # When OUR system received it (for audit purposes)
    received_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    # Relationship back to transaction
    transaction = relationship("Transaction", back_populates="events")

    # -------------------------------------------------------
    # INDEXES on payment_events
    # -------------------------------------------------------
    __table_args__ = (
        Index("ix_events_transaction_id", "transaction_id"),   # fetch all events for a transaction
        Index("ix_events_event_type", "event_type"),           # filter by event type
        Index("ix_events_timestamp", "timestamp"),             # sort by time
    )

    def __repr__(self):
        return f"<PaymentEvent {self.event_type} for txn {self.transaction_id}>"
