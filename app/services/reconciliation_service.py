"""
reconciliation_service.py
--------------------------
Business logic for reconciliation queries.

This file is SQL-heavy by design. Setu specifically evaluates:
  - aggregations happening in SQL (not Python loops)
  - correct use of GROUP BY, SUM, COUNT, CASE WHEN
  - clean discrepancy detection logic

Three discrepancy types we detect:

1. settled_after_failure
   payment_status=failed AND settlement_status=settled
   WHY IT MATTERS: A failed payment should never have a settlement.
   This means either: fraud, a double-credit, or a processing bug.

2. processed_not_settled
   payment_status=processed AND settlement_status=pending
   WHY IT MATTERS: The payment went through but the merchant never received money.
   This is a real financial problem for the merchant.

3. stale_initiated
   status=initiated AND only 1 event exists (just payment_initiated, nothing else)
   WHY IT MATTERS: Payment was started but went completely silent.
   Could be a dropped message, a network failure, or a partner bug.

4. duplicate_state_transition
   The upstream system sent multiple events of the EXACT SAME type (e.g. 2 processed webhooks) with unique IDs.
   WHY IT MATTERS: True event sourcing requires logging the anomaly without dropping data.
"""

from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func, case, text

from app import models


# ===========================================================
# RECONCILIATION SUMMARY
# ===========================================================

def get_summary(db: Session, merchant_id: str = None, date_from: datetime = None, date_to: datetime = None):
    """
    Returns three aggregated views of transaction data:
    1. by_merchant - totals grouped per merchant
    2. by_status   - counts and amounts per status
    3. by_date     - daily breakdown

    All aggregations happen in SQL using GROUP BY + CASE WHEN.
    """

    # Base filter conditions (reused across all 3 queries)
    def apply_base_filters(query):
        if merchant_id:
            query = query.filter(models.Transaction.merchant_id == merchant_id)
        if date_from:
            query = query.filter(models.Transaction.created_at >= date_from)
        if date_to:
            query = query.filter(models.Transaction.created_at <= date_to)
        return query

    # ---------------------------------------------------
    # 1. Totals (for the summary header)
    # ---------------------------------------------------
    total_q = apply_base_filters(db.query(
        func.count(models.Transaction.transaction_id).label("total_transactions"),
        func.coalesce(func.sum(models.Transaction.amount), 0).label("total_amount"),
        func.coalesce(
            func.sum(case((models.Transaction.settlement_status == "settled", models.Transaction.amount), else_=0)),
            0
        ).label("total_settled_amount"),
    ))
    totals = total_q.one()

    # ---------------------------------------------------
    # 2. By Merchant
    # SQL concept: JOIN + GROUP BY + CASE WHEN for conditional aggregation
    # ---------------------------------------------------
    merchant_q = apply_base_filters(
        db.query(
            models.Merchant.merchant_id,
            models.Merchant.merchant_name,
            func.count(models.Transaction.transaction_id).label("total_transactions"),
            func.coalesce(func.sum(models.Transaction.amount), 0).label("total_amount"),
            func.count(case((models.Transaction.settlement_status == "settled", 1))).label("settled_count"),
            func.coalesce(
                func.sum(case((models.Transaction.settlement_status == "settled", models.Transaction.amount), else_=0)),
                0
            ).label("settled_amount"),
            func.count(case((models.Transaction.status == "processed", 1))).label("processed_count"),
            func.count(case((models.Transaction.status == "failed", 1))).label("failed_count"),
            func.count(case((models.Transaction.status == "initiated", 1))).label("initiated_count"),
        )
        .join(models.Merchant, models.Transaction.merchant_id == models.Merchant.merchant_id)
        .group_by(models.Merchant.merchant_id, models.Merchant.merchant_name)
        .order_by(func.sum(models.Transaction.amount).desc())
    )
    merchant_rows = merchant_q.all()

    by_merchant = []
    for row in merchant_rows:
        total = row.total_transactions or 0
        settled = row.settled_count or 0
        rate = round((settled / total * 100), 2) if total > 0 else 0.0
        by_merchant.append({
            "merchant_id": row.merchant_id,
            "merchant_name": row.merchant_name,
            "total_transactions": total,
            "total_amount": Decimal(str(row.total_amount or 0)),
            "settled_count": settled,
            "settled_amount": Decimal(str(row.settled_amount or 0)),
            "processed_count": row.processed_count or 0,
            "failed_count": row.failed_count or 0,
            "initiated_count": row.initiated_count or 0,
            "settlement_rate_pct": rate,
        })

    # ---------------------------------------------------
    # 3. By Status
    # SQL concept: GROUP BY on a single column
    # ---------------------------------------------------
    status_q = apply_base_filters(
        db.query(
            models.Transaction.status,
            func.count(models.Transaction.transaction_id).label("count"),
            func.coalesce(func.sum(models.Transaction.amount), 0).label("total_amount"),
        )
        .group_by(models.Transaction.status)
        .order_by(func.count(models.Transaction.transaction_id).desc())
    )
    by_status = [
        {
            "status": row.status,
            "count": row.count,
            "total_amount": Decimal(str(row.total_amount or 0)),
        }
        for row in status_q.all()
    ]

    # ---------------------------------------------------
    # 4. By Date
    # SQL concept: DATE() function to truncate timestamp to day
    # We use SQLAlchemy text() for the date-cast since SQLite
    # and PostgreSQL handle this differently
    # ---------------------------------------------------
    date_q = apply_base_filters(
        db.query(
            func.date(models.Transaction.created_at).label("date"),
            func.count(models.Transaction.transaction_id).label("total_transactions"),
            func.coalesce(func.sum(models.Transaction.amount), 0).label("total_amount"),
            func.count(case((models.Transaction.settlement_status == "settled", 1))).label("settled_count"),
            func.coalesce(
                func.sum(case((models.Transaction.settlement_status == "settled", models.Transaction.amount), else_=0)),
                0
            ).label("settled_amount"),
            func.count(case((models.Transaction.status == "failed", 1))).label("failed_count"),
            func.count(case((models.Transaction.status == "processed", 1))).label("processed_count"),
        )
        .group_by(func.date(models.Transaction.created_at))
        .order_by(func.date(models.Transaction.created_at).desc())
    )
    by_date = [
        {
            "date": str(row.date),
            "total_transactions": row.total_transactions or 0,
            "total_amount": Decimal(str(row.total_amount or 0)),
            "settled_count": row.settled_count or 0,
            "settled_amount": Decimal(str(row.settled_amount or 0)),
            "failed_count": row.failed_count or 0,
            "processed_count": row.processed_count or 0,
        }
        for row in date_q.all()
    ]

    return {
        "generated_at": datetime.now(timezone.utc),
        "total_transactions": totals.total_transactions or 0,
        "total_amount": Decimal(str(totals.total_amount or 0)),
        "total_settled_amount": Decimal(str(totals.total_settled_amount or 0)),
        "by_merchant": by_merchant,
        "by_status": by_status,
        "by_date": by_date,
    }


# ===========================================================
# DISCREPANCY DETECTION
# ===========================================================

def get_discrepancies(db: Session, merchant_id: str = None, discrepancy_type: str = None):
    """
    Detects and returns transactions with inconsistent payment/settlement state.

    Three types detected:

    Type 1 - settled_after_failure
      payment_status = failed AND settlement_status = settled
      This is an IMPOSSIBLE state in a correct system.

    Type 2 - processed_not_settled
      payment_status = processed AND settlement_status = pending
      Payment went through but merchant has not been paid yet.

    Type 3 - stale_initiated
      status = initiated AND transaction has only 1 event (payment_initiated)
      Payment was started but completely silent with no followup.

    Type 4 - duplicate_state_transition
      The transaction has multiple events of the exact same event_type.
      The bank/gateway sent erratic duplicate states.
    """

    all_discrepancies = []

    # ---------------------------------------------------
    # TYPE 1: Settled after failure (impossible state)
    # ---------------------------------------------------
    if not discrepancy_type or discrepancy_type == "settled_after_failure":
        q = db.query(models.Transaction).join(models.Merchant)
        if merchant_id:
            q = q.filter(models.Transaction.merchant_id == merchant_id)
        q = q.filter(
            models.Transaction.payment_status == "failed",
            models.Transaction.settlement_status == "settled",
        )
        for txn in q.all():
            all_discrepancies.append(_build_discrepancy(txn, "settled_after_failure",
                "Payment was marked as FAILED but a settlement was recorded. "
                "This is an impossible state — investigate immediately for potential double credit or fraud."))

    # ---------------------------------------------------
    # TYPE 2: Processed but not settled
    # ---------------------------------------------------
    if not discrepancy_type or discrepancy_type == "processed_not_settled":
        q = db.query(models.Transaction).join(models.Merchant)
        if merchant_id:
            q = q.filter(models.Transaction.merchant_id == merchant_id)
        q = q.filter(
            models.Transaction.payment_status == "processed",
            models.Transaction.settlement_status == "pending",
        )
        for txn in q.all():
            all_discrepancies.append(_build_discrepancy(txn, "processed_not_settled",
                "Payment was successfully PROCESSED but no settlement has been recorded. "
                "The merchant is owed money that has not been credited yet."))

    # ---------------------------------------------------
    # TYPE 3: Stale initiated (subquery to count events)
    # ---------------------------------------------------
    if not discrepancy_type or discrepancy_type == "stale_initiated":
        # Subquery: count events per transaction
        event_count_sub = (
            db.query(
                models.PaymentEvent.transaction_id,
                func.count(models.PaymentEvent.id).label("event_count"),
            )
            .group_by(models.PaymentEvent.transaction_id)
            .subquery()
        )

        q = (
            db.query(models.Transaction)
            .join(models.Merchant)
            .join(event_count_sub, models.Transaction.transaction_id == event_count_sub.c.transaction_id)
            .filter(
                models.Transaction.status == "initiated",
                event_count_sub.c.event_count == 1,   # only payment_initiated, nothing else
            )
        )
        if merchant_id:
            q = q.filter(models.Transaction.merchant_id == merchant_id)

        for txn in q.all():
            all_discrepancies.append(_build_discrepancy(txn, "stale_initiated",
                "Payment was INITIATED but no follow-up event (processed/failed) was ever received. "
                "The transaction is stuck — likely a dropped message or partner system failure."))

    # ---------------------------------------------------
    # TYPE 4: Duplicate State Transition (Anomaly Detection)
    # ---------------------------------------------------
    if not discrepancy_type or discrepancy_type == "duplicate_state_transition":
        # Subquery: find transaction_ids that have > 1 of the same event_type
        duplicate_event_sub = (
            db.query(models.PaymentEvent.transaction_id)
            .group_by(models.PaymentEvent.transaction_id, models.PaymentEvent.event_type)
            .having(func.count(models.PaymentEvent.id) > 1)
            .subquery()
        )

        q = (
            db.query(models.Transaction)
            .join(models.Merchant)
            .join(duplicate_event_sub, models.Transaction.transaction_id == duplicate_event_sub.c.transaction_id)
        )
        if merchant_id:
            q = q.filter(models.Transaction.merchant_id == merchant_id)

        # distinct() is needed because a transaction might have multiple duplicate types
        for txn in q.distinct().all():
            all_discrepancies.append(_build_discrepancy(txn, "duplicate_state_transition",
                "The upstream partner sent multiple webhook events for the exact same state (e.g. processed). "
                "The ledger accepted them as historical truth, but this is a buggy upstream anomaly."))

    # Build breakdown counts
    breakdown = {
        "settled_after_failure": sum(1 for d in all_discrepancies if d["discrepancy_type"] == "settled_after_failure"),
        "processed_not_settled": sum(1 for d in all_discrepancies if d["discrepancy_type"] == "processed_not_settled"),
        "stale_initiated":       sum(1 for d in all_discrepancies if d["discrepancy_type"] == "stale_initiated"),
        "duplicate_state_transition": sum(1 for d in all_discrepancies if d["discrepancy_type"] == "duplicate_state_transition"),
    }

    return {
        "generated_at": datetime.now(timezone.utc),
        "total_discrepancies": len(all_discrepancies),
        "breakdown": breakdown,
        "discrepancies": all_discrepancies,
    }


def _build_discrepancy(txn: models.Transaction, discrepancy_type: str, description: str) -> dict:
    """Helper to build a discrepancy dict from a Transaction ORM object."""
    merchant_name = txn.merchant.merchant_name if txn.merchant else None
    return {
        "transaction_id": txn.transaction_id,
        "merchant_id": txn.merchant_id,
        "merchant_name": merchant_name,
        "amount": txn.amount,
        "currency": txn.currency,
        "payment_status": txn.payment_status,
        "settlement_status": txn.settlement_status,
        "status": txn.status,
        "discrepancy_type": discrepancy_type,
        "discrepancy_description": description,
        "created_at": txn.created_at,
        "updated_at": txn.updated_at,
    }
