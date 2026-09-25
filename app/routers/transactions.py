"""
routers/transactions.py
-----------------------
GET /transactions        - list with filters, pagination, sorting
GET /transactions/{id}   - full detail with event history
"""

import math
from typing import Optional, Literal
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import asc, desc

from app.database import get_db
from app import models
from app.schemas import (
    PaginatedTransactions,
    TransactionSummary,
    TransactionDetail,
    EventInHistory,
)

router = APIRouter(prefix="/transactions", tags=["Transactions"])


# ===========================================================
# GET /transactions
# ===========================================================
@router.get(
    "",
    response_model=PaginatedTransactions,
    summary="List transactions with filters and pagination",
    description="""
    Returns a paginated list of transactions.

    **Filters (all optional):**
    - `merchant_id`  — filter by merchant e.g. `merchant_1`
    - `status`       — filter by status: initiated | processed | failed | settled
    - `date_from`    — transactions created on or after this datetime (ISO 8601)
    - `date_to`      — transactions created on or before this datetime (ISO 8601)

    **Pagination:**
    - `page`         — page number, starts at 1 (default: 1)
    - `page_size`    — results per page, max 100 (default: 20)

    **Sorting:**
    - `sort_by`      — field to sort: created_at | amount | status | updated_at (default: created_at)
    - `sort_order`   — asc or desc (default: desc)
    """,
)
def list_transactions(
    merchant_id: Optional[str] = Query(default=None, description="Filter by merchant ID"),
    status: Optional[Literal["initiated", "processed", "failed", "settled"]] = Query(
        default=None, description="Filter by transaction status"
    ),
    date_from: Optional[datetime] = Query(default=None, description="Start date filter (ISO 8601)"),
    date_to: Optional[datetime] = Query(default=None, description="End date filter (ISO 8601)"),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    sort_by: Literal["created_at", "amount", "status", "updated_at"] = Query(
        default="created_at", description="Sort field"
    ),
    sort_order: Literal["asc", "desc"] = Query(default="desc", description="Sort direction"),
    db: Session = Depends(get_db),
):
    # ---------------------------------------------------
    # Build the base query
    # All filtering happens in SQL — not in Python loops!
    # ---------------------------------------------------
    query = db.query(models.Transaction)

    # Apply filters
    if merchant_id:
        query = query.filter(models.Transaction.merchant_id == merchant_id)

    if status:
        query = query.filter(models.Transaction.status == status)

    if date_from:
        query = query.filter(models.Transaction.created_at >= date_from)

    if date_to:
        query = query.filter(models.Transaction.created_at <= date_to)

    # Get total count BEFORE pagination (needed for total_pages calculation)
    total = query.count()

    # Apply sorting
    sort_column = getattr(models.Transaction, sort_by)
    if sort_order == "desc":
        query = query.order_by(desc(sort_column))
    else:
        query = query.order_by(asc(sort_column))

    # Apply pagination — OFFSET and LIMIT happen in SQL
    offset = (page - 1) * page_size
    transactions = query.offset(offset).limit(page_size).all()

    # Build response with merchant names (joined from merchant table)
    items = []
    for txn in transactions:
        merchant_name = txn.merchant.merchant_name if txn.merchant else None
        items.append(TransactionSummary(
            transaction_id=txn.transaction_id,
            merchant_id=txn.merchant_id,
            merchant_name=merchant_name,
            amount=txn.amount,
            currency=txn.currency,
            status=txn.status,
            payment_status=txn.payment_status,
            settlement_status=txn.settlement_status,
            created_at=txn.created_at,
            updated_at=txn.updated_at,
        ))

    return PaginatedTransactions(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total > 0 else 0,
        items=items,
    )


# ===========================================================
# GET /transactions/{transaction_id}
# ===========================================================
@router.get(
    "/{transaction_id}",
    response_model=TransactionDetail,
    summary="Fetch full transaction details with event history",
    description="""
    Returns complete details for a single transaction including:
    - Current payment and settlement status
    - Merchant information
    - Full chronological event history
    """,
)
def get_transaction(
    transaction_id: str,
    db: Session = Depends(get_db),
):
    # Fetch transaction (with merchant relationship loaded)
    transaction = db.query(models.Transaction).filter(
        models.Transaction.transaction_id == transaction_id
    ).first()

    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction '{transaction_id}' not found",
        )

    # Fetch event history sorted by timestamp ascending
    events = db.query(models.PaymentEvent).filter(
        models.PaymentEvent.transaction_id == transaction_id
    ).order_by(models.PaymentEvent.timestamp.asc()).all()

    merchant_name = transaction.merchant.merchant_name if transaction.merchant else None

    event_history = [
        EventInHistory(
            event_id=e.event_id,
            event_type=e.event_type,
            amount=e.amount,
            currency=e.currency,
            timestamp=e.timestamp,
            received_at=e.received_at,
        )
        for e in events
    ]

    return TransactionDetail(
        transaction_id=transaction.transaction_id,
        merchant_id=transaction.merchant_id,
        merchant_name=merchant_name,
        amount=transaction.amount,
        currency=transaction.currency,
        status=transaction.status,
        payment_status=transaction.payment_status,
        settlement_status=transaction.settlement_status,
        created_at=transaction.created_at,
        updated_at=transaction.updated_at,
        events=event_history,
    )
