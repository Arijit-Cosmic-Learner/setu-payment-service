"""
tests/test_events.py
--------------------
Tests for POST /events

Covers:
- Happy path: valid event ingestion
- Idempotency: sending the same event twice
- Invalid payloads: missing fields, bad event_type
- State machine: status transitions across multiple events
"""

import pytest


class TestPostEvents:

    def test_ingest_new_event_returns_created(self, client, sample_event):
        """A brand new event should be stored and return ingestion_status=created."""
        resp = client.post("/events", json=sample_event)

        assert resp.status_code == 200
        body = resp.json()
        assert body["event_id"] == "test-evt-001"
        assert body["ingestion_status"] == "created"
        assert body["event_type"] == "payment_initiated"
        assert body["merchant_id"] == "merchant_1"

    def test_idempotency_duplicate_event_returns_already_processed(self, client, sample_event):
        """
        THE MOST IMPORTANT TEST.
        Sending the same event_id twice must NOT create a duplicate.
        The second call must return ingestion_status=already_processed.
        This proves our idempotency guard works.
        """
        # First call
        resp1 = client.post("/events", json=sample_event)
        assert resp1.json()["ingestion_status"] == "created"

        # Second call with IDENTICAL payload
        resp2 = client.post("/events", json=sample_event)
        assert resp2.status_code == 200
        assert resp2.json()["ingestion_status"] == "already_processed"

    def test_duplicate_does_not_create_extra_db_records(self, client, db, sample_event):
        """After two identical calls, only ONE record should exist in payment_events."""
        from app.models import PaymentEvent

        client.post("/events", json=sample_event)
        client.post("/events", json=sample_event)

        count = db.query(PaymentEvent).filter(
            PaymentEvent.event_id == "test-evt-001"
        ).count()
        assert count == 1, f"Expected 1 event record, got {count}"

    def test_invalid_event_type_returns_422(self, client, sample_event):
        """An unrecognised event_type should be rejected with HTTP 422 Unprocessable Entity."""
        sample_event["event_type"] = "refund_initiated"  # not in our allowed list
        resp = client.post("/events", json=sample_event)
        assert resp.status_code == 422

    def test_missing_required_field_returns_422(self, client):
        """A payload missing event_id must be rejected."""
        resp = client.post("/events", json={"event_type": "payment_initiated"})
        assert resp.status_code == 422

    def test_negative_amount_returns_422(self, client, sample_event):
        """Negative amounts must be rejected (amount must be > 0)."""
        sample_event["amount"] = -100
        resp = client.post("/events", json=sample_event)
        assert resp.status_code == 422

    def test_state_machine_happy_path(self, client, full_transaction_events):
        """
        After initiated -> processed -> settled, the transaction status must be settled
        and settlement_status must be settled.
        """
        for event in full_transaction_events:
            client.post("/events", json=event)

        # Fetch the transaction to verify final state
        resp = client.get("/transactions/txn-full")
        assert resp.status_code == 200
        txn = resp.json()
        assert txn["status"] == "settled"
        assert txn["payment_status"] == "processed"
        assert txn["settlement_status"] == "settled"

    def test_state_machine_failed_path(self, client):
        """After initiated -> failed, status must be failed."""
        client.post("/events", json={
            "event_id": "f-init", "event_type": "payment_initiated",
            "transaction_id": "txn-fail", "merchant_id": "merchant_1",
            "merchant_name": "QuickMart", "amount": 100, "currency": "INR",
            "timestamp": "2026-01-10T10:00:00+00:00"
        })
        client.post("/events", json={
            "event_id": "f-fail", "event_type": "payment_failed",
            "transaction_id": "txn-fail", "merchant_id": "merchant_1",
            "merchant_name": "QuickMart", "amount": 100, "currency": "INR",
            "timestamp": "2026-01-10T10:05:00+00:00"
        })
        resp = client.get("/transactions/txn-fail")
        txn = resp.json()
        assert txn["status"] == "failed"
        assert txn["payment_status"] == "failed"
        assert txn["settlement_status"] == "pending"

    def test_event_history_ordered_by_timestamp(self, client, full_transaction_events):
        """Events in GET /transactions/{id} must be ordered chronologically."""
        for event in full_transaction_events:
            client.post("/events", json=event)

        resp = client.get("/transactions/txn-full")
        events = resp.json()["events"]
        assert len(events) == 3
        assert events[0]["event_type"] == "payment_initiated"
        assert events[1]["event_type"] == "payment_processed"
        assert events[2]["event_type"] == "settled"
