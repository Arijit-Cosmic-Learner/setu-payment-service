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
- They don't always match! e.g. we never expose internal DB IDs in the API.
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, field_validator


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
        description="'created' = new event stored. 'already_processed' = duplicate, ignored safely."
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
    """A single event in a transaction's event history."""
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
    Used in GET /transactions list — one row per transaction.
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
    Used in GET /transactions/{id} — full detail.
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
    This lets the caller know how many pages exist.
    """
    total: int = Field(description="Total number of matching transactions")
    page: int = Field(description="Current page number (1-indexed)")
    page_size: int = Field(description="Number of items per page")
    total_pages: int = Field(description="Total number of pages")
    items: List[TransactionSummary]


# ===========================================================
# QUERY PARAMETER SCHEMAS
# ===========================================================

class TransactionFilters(BaseModel):
    """
    All supported filters for GET /transactions.
    FastAPI reads these from the URL query string automatically.
    Example: GET /transactions?merchant_id=merchant_1&status=failed&page=2
    """
    merchant_id: Optional[str] = Field(default=None, description="Filter by merchant")
    status: Optional[Literal["initiated", "processed", "failed", "settled"]] = Field(
        default=None, description="Filter by current transaction status"
    )
    date_from: Optional[datetime] = Field(default=None, description="Filter transactions from this date (ISO 8601)")
    date_to: Optional[datetime] = Field(default=None, description="Filter transactions up to this date (ISO 8601)")
    page: int = Field(default=1, ge=1, description="Page number (starts at 1)")
    page_size: int = Field(default=20, ge=1, le=100, description="Results per page (max 100)")
    sort_by: Literal["created_at", "amount", "status", "updated_at"] = Field(
        default="created_at", description="Field to sort by"
    )
    sort_order: Literal["asc", "desc"] = Field(default="desc", description="Sort direction")


# ===========================================================
# ERROR SCHEMA
# ===========================================================

class ErrorResponse(BaseModel):
    """Standard error response shape."""
    detail: str
    error_code: Optional[str] = None
