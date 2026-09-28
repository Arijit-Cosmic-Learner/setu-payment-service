"""
routers/reconciliation.py
--------------------------
GET /reconciliation/summary       - aggregated financials by merchant, date, status
GET /reconciliation/discrepancies - transactions with inconsistent payment/settlement state

These are the most analytically complex endpoints in the service.
All heavy lifting is done in SQL (reconciliation_service.py), not in Python loops.
"""

from typing import Optional, Literal
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import ReconciliationSummaryResponse, DiscrepanciesResponse
from app.services.reconciliation_service import get_summary, get_discrepancies

router = APIRouter(prefix="/reconciliation", tags=["Reconciliation"])


# ===========================================================
# GET /reconciliation/summary
# ===========================================================
@router.get(
    "/summary",
    response_model=ReconciliationSummaryResponse,
    summary="Reconciliation summary grouped by merchant, date, and status",
    description="""
    Returns a comprehensive financial summary with three views:

    **by_merchant** - per-merchant totals including:
    - Total transaction count and amount
    - Settled count and settled amount
    - Failed and processed counts
    - Settlement rate percentage

    **by_status** - transaction counts and amounts per status
    (initiated, processed, failed, settled)

    **by_date** - daily breakdown of transaction activity

    All aggregations are computed in SQL using GROUP BY and CASE WHEN.

    **Optional filters:**
    - `merchant_id` - narrow to a single merchant
    - `date_from` / `date_to` - limit to a date range
    """,
)
def reconciliation_summary(
    merchant_id: Optional[str] = Query(default=None, description="Filter by merchant ID"),
    date_from: Optional[datetime] = Query(default=None, description="Start date (ISO 8601)"),
    date_to: Optional[datetime] = Query(default=None, description="End date (ISO 8601)"),
    db: Session = Depends(get_db),
):
    result = get_summary(db=db, merchant_id=merchant_id, date_from=date_from, date_to=date_to)
    return result


# ===========================================================
# GET /reconciliation/discrepancies
# ===========================================================
@router.get(
    "/discrepancies",
    response_model=DiscrepanciesResponse,
    summary="List transactions with payment/settlement inconsistencies",
    description="""
    Returns transactions where payment state and settlement state are inconsistent.

    **Three discrepancy types detected:**

    | Type | Condition | Why It Matters |
    |------|-----------|----------------|
    | `settled_after_failure` | payment_status=failed AND settlement_status=settled | Impossible state — potential fraud or double credit |
    | `processed_not_settled` | payment_status=processed AND settlement_status=pending | Merchant is owed money not yet credited |
    | `stale_initiated` | status=initiated AND only 1 event received | Payment stuck — dropped message or partner bug |

    **Optional filters:**
    - `merchant_id` - narrow to a specific merchant
    - `discrepancy_type` - filter to one specific type
    """,
)
def reconciliation_discrepancies(
    merchant_id: Optional[str] = Query(default=None, description="Filter by merchant ID"),
    discrepancy_type: Optional[Literal[
        "settled_after_failure",
        "processed_not_settled",
        "stale_initiated",
        "duplicate_state_transition",
        "over_settled_anomaly"
    ]] = Query(default=None, description="Filter by discrepancy type"),
    db: Session = Depends(get_db),
):
    result = get_discrepancies(db=db, merchant_id=merchant_id, discrepancy_type=discrepancy_type)
    return result
