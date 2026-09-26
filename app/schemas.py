"""
schemas.py
----------
Pydantic models that define the SHAPE of data going IN and OUT of our API.

Think of schemas as the "contract" between the API and its callers:
- Request schemas: what JSON the caller must send us
- Response schemas: what JSON we send back

WHY separate from models.py?
- models.py = database table shape (how data is STORED)
- schemas.py = API shape (how data is COMMUNICATED)
- They do not always match! e.g. we never expose internal DB IDs in the API.
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Literal, Any, Dict
from pydantic import BaseModel, Field


# ===========================================================
# EVENT SCHEMAS
# ===========================================================

class EventCreate(BaseModel):
    """
    Schema for POST /events request body.
    Exactly mirrors the shape of sample_events.json.
    """
    event_id: str = Field(..., description="Unique identifier for this event (UUID)")
    event_type: Literal["payment_initiated", "payment_processed", "payment_failed", "settled"] = Field(
        ..., description="Type of payment lifecycle event"
    )
    transaction_id: str = Field(..., description="UUID linking this event to a transaction")
    merchant_id: str = Field(..., description="Merchant identifier e.g. merchant_1")
    merchant_name: str = Field(..., description="Human-readable merchant name e.g. QuickMart")
    amount: Decimal = Field(..., gt=0, description="Transaction amount in the given currency")
    currency: str = Field(default="INR", description="ISO currency code")
    timestamp: datetime = Field(..., description="When the event occurred in the payment system")


class EventResponse(BaseModel):
    """Response schema after ingesting an event."""
    event_id: str
    event_type: str
    transaction_id: str
    merchant_id: str
    amount: Decimal
    currency: str
    timestamp: datetime
    received_at: datetime
    ingestion_status: Literal["created", "already_processed"] = Field(
        description="created = new event stored. already_processed = duplicate, ignored safely."
    )

    class Config:
        from_attributes = True


# ===========================================================
# MERCHANT SCHEMAS
# ===========================================================

class MerchantInfo(BaseModel):
    """Embedded merchant info returned inside transaction responses."""
    merchant_id: str
    merchant_name: str

    class Config:
        from_attributes = True


# ===========================================================
# TRANSACTION SCHEMAS
# ===========================================================

class EventInHistory(BaseModel):
    """A single event in a transactions event history."""
    event_id: str
    event_type: str
    amount: Decimal
    currency: str
    timestamp: datetime
    received_at: datetime

    class Config:
        from_attributes = True


class TransactionSummary(BaseModel):
    """
    Used in GET /transactions list - one row per transaction.
    Lightweight: no event history included.
    """
    transaction_id: str
    merchant_id: str
    merchant_name: Optional[str] = None
    amount: Decimal
    currency: str
    status: str
    payment_status: str
    settlement_status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TransactionDetail(TransactionSummary):
    """
    Used in GET /transactions/{id} - full detail.
    Includes complete event history for this transaction.
    """
    events: List[EventInHistory] = []

    class Config:
        from_attributes = True


# ===========================================================
# PAGINATION WRAPPER
# ===========================================================

class PaginatedTransactions(BaseModel):
    """
    Standard pagination envelope for GET /transactions.
    Every paginated API should return: total, page, page_size, items.
    """
    total: int = Field(description="Total number of matching transactions")
    page: int = Field(description="Current page number (1-indexed)")
    page_size: int = Field(description="Number of items per page")
    total_pages: int = Field(description="Total number of pages")
    items: List[TransactionSummary]


# ===========================================================
# RECONCILIATION SCHEMAS
# ===========================================================

class MerchantSummary(BaseModel):
    """
    Aggregated stats for a single merchant.
    Used in GET /reconciliation/summary -> by_merchant section.
    """
    merchant_id: str
    merchant_name: str
    total_transactions: int
    total_amount: Decimal
    settled_count: int
    settled_amount: Decimal
    processed_count: int
    failed_count: int
    initiated_count: int
    settlement_rate_pct: float = Field(description="Percentage of transactions that are settled")


class StatusBreakdown(BaseModel):
    """Count and amount for each transaction status."""
    status: str
    count: int
    total_amount: Decimal


class DateSummary(BaseModel):
    """Daily aggregation row."""
    date: str
    total_transactions: int
    total_amount: Decimal
    settled_count: int
    settled_amount: Decimal
    failed_count: int
    processed_count: int


class ReconciliationSummaryResponse(BaseModel):
    """
    Full response for GET /reconciliation/summary.
    Contains three views of the same data:
    - by_merchant: one row per merchant
    - by_status:   one row per status value
    - by_date:     one row per calendar date
    """
    generated_at: datetime
    total_transactions: int
    total_amount: Decimal
    total_settled_amount: Decimal
    by_merchant: List[MerchantSummary]
    by_status: List[StatusBreakdown]
    by_date: List[DateSummary]


class DiscrepancyItem(BaseModel):
    """
    A single transaction flagged as having a discrepancy.
    discrepancy_type tells you WHAT is wrong.
    discrepancy_description tells you WHY it matters.
    """
    transaction_id: str
    merchant_id: str
    merchant_name: Optional[str] = None
    amount: Decimal
    currency: str
    payment_status: str
    settlement_status: str
    status: str
    discrepancy_type: Literal[
        "settled_after_failure",
        "processed_not_settled",
        "stale_initiated"
    ]
    discrepancy_description: str
    created_at: datetime
    updated_at: datetime


class DiscrepancyBreakdown(BaseModel):
    """Count of each discrepancy type - for a quick overview."""
    settled_after_failure: int = Field(description="Payment failed but settlement was recorded (impossible state)")
    processed_not_settled: int = Field(description="Payment processed but no settlement recorded")
    stale_initiated: int = Field(description="Payment initiated but stuck with no follow-up event")


class DiscrepanciesResponse(BaseModel):
    """Full response for GET /reconciliation/discrepancies."""
    generated_at: datetime
    total_discrepancies: int
    breakdown: DiscrepancyBreakdown
    discrepancies: List[DiscrepancyItem]


# ===========================================================
# ERROR SCHEMA
# ===========================================================

class ErrorResponse(BaseModel):
    """Standard error response shape."""
    detail: str
    error_code: Optional[str] = None
