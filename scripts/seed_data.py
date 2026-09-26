"""
scripts/seed_data.py
--------------------
Downloads sample_events.json from the Setu GitHub repo and loads
all 10,000 events into the database using the event ingestion service.

WHY use the service layer instead of direct SQL inserts?
- Ensures all business logic runs (state machine, idempotency)
- Exactly mirrors what the real POST /events endpoint does
- Guarantees the seeded data is in a consistent state

Run this script:
    python scripts/seed_data.py

Safe to run multiple times — idempotency handles duplicates.
"""

import sys
import os
import json
import urllib.request
from datetime import datetime

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from app.database import SessionLocal, engine, Base
from app.models import Merchant, Transaction, PaymentEvent
from app.services.event_service import ingest_event
from app.schemas import EventCreate

# URL for the official sample data
SAMPLE_DATA_URL = "https://raw.githubusercontent.com/SetuHQ/hiring-assignments/refs/heads/main/solutions-engineer/sample_events.json"
LOCAL_FILE = os.path.join(os.path.dirname(__file__), "..", "sample_events.json")


def download_sample_data() -> list:
    """Download sample_events.json if not already present locally."""
    local_path = os.path.abspath(LOCAL_FILE)

    if os.path.exists(local_path):
        print(f"Found local sample_events.json - loading from disk...")
        with open(local_path, "r", encoding="utf-8") as f:
            return json.load(f)

    print(f"Downloading sample_events.json from GitHub...")
    try:
        with urllib.request.urlopen(SAMPLE_DATA_URL, timeout=30) as response:
            content = response.read().decode("utf-8")
        events = json.loads(content)
        # Save locally for future runs
        with open(local_path, "w", encoding="utf-8") as f:
            json.dump(events, f)
        print(f"Downloaded and saved {len(events)} events to sample_events.json")
        return events
    except Exception as e:
        print(f"Download failed: {e}")
        print("Please download sample_events.json manually from:")
        print(SAMPLE_DATA_URL)
        sys.exit(1)


def seed(db: Session, events: list):
    """Load all events into the database."""
    total = len(events)
    created = 0
    duplicates = 0
    errors = 0

    print(f"\nSeeding {total} events into database...")
    print("-" * 50)

    for i, raw_event in enumerate(events, 1):
        try:
            event = EventCreate(
                event_id=raw_event["event_id"],
                event_type=raw_event["event_type"],
                transaction_id=raw_event["transaction_id"],
                merchant_id=raw_event["merchant_id"],
                merchant_name=raw_event["merchant_name"],
                amount=raw_event["amount"],
                currency=raw_event.get("currency", "INR"),
                timestamp=raw_event["timestamp"],
            )
            result = ingest_event(db=db, event=event)

            if result["ingestion_status"] == "created":
                created += 1
            else:
                duplicates += 1

        except Exception as e:
            errors += 1
            print(f"  ERROR on event {raw_event.get('event_id', '?')}: {e}")

        # Progress update every 1000 events
        if i % 1000 == 0 or i == total:
            pct = round(i / total * 100)
            print(f"  Progress: {i}/{total} ({pct}%) | created={created} | duplicates={duplicates} | errors={errors}")

    return created, duplicates, errors


def print_stats(db: Session):
    """Print a summary of what is now in the database."""
    print("\n" + "=" * 50)
    print("DATABASE STATS AFTER SEEDING")
    print("=" * 50)

    merchant_count = db.query(Merchant).count()
    txn_count = db.query(Transaction).count()
    event_count = db.query(PaymentEvent).count()

    print(f"  Merchants   : {merchant_count}")
    print(f"  Transactions: {txn_count}")
    print(f"  Events      : {event_count}")

    print("\n  Transaction status breakdown:")
    from sqlalchemy import func
    status_counts = db.query(Transaction.status, func.count(Transaction.transaction_id)).group_by(Transaction.status).all()
    for status, count in status_counts:
        print(f"    {status:<12}: {count}")

    print("\n  Settlement status breakdown:")
    settlement_counts = db.query(Transaction.settlement_status, func.count(Transaction.transaction_id)).group_by(Transaction.settlement_status).all()
    for status, count in settlement_counts:
        print(f"    {status:<12}: {count}")

    print()


def main():
    start = datetime.now()
    print("=" * 50)
    print("SETU PAYMENT SERVICE - Data Seeder")
    print("=" * 50)

    # Ensure tables exist
    Base.metadata.create_all(bind=engine)

    # Load events
    events = download_sample_data()

    # Seed into DB
    db = SessionLocal()
    try:
        created, duplicates, errors = seed(db, events)
        print_stats(db)

        elapsed = (datetime.now() - start).total_seconds()
        print(f"Seeding complete in {elapsed:.1f}s")
        print(f"  Created  : {created}")
        print(f"  Duplicates: {duplicates}")
        print(f"  Errors   : {errors}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
