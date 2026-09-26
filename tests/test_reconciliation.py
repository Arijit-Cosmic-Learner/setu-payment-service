"""
tests/test_reconciliation.py
-----------------------------
Tests for GET /reconciliation/summary and GET /reconciliation/discrepancies
"""

import pytest


def seed_discrepancy_scenarios(client):
    """
    Seeds 4 transactions covering all scenarios:
    - 1 happy path (settled)
    - 1 settled_after_failure discrepancy
    - 1 processed_not_settled discrepancy
    - 1 stale_initiated discrepancy
    """
    events = [
        # HAPPY PATH
        {"event_id":"hp1","event_type":"payment_initiated","transaction_id":"txn-happy","merchant_id":"merchant_1","merchant_name":"QuickMart","amount":10000,"currency":"INR","timestamp":"2026-01-01T10:00:00+00:00"},
        {"event_id":"hp2","event_type":"payment_processed","transaction_id":"txn-happy","merchant_id":"merchant_1","merchant_name":"QuickMart","amount":10000,"currency":"INR","timestamp":"2026-01-01T10:05:00+00:00"},
        {"event_id":"hp3","event_type":"settled","transaction_id":"txn-happy","merchant_id":"merchant_1","merchant_name":"QuickMart","amount":10000,"currency":"INR","timestamp":"2026-01-01T12:00:00+00:00"},
        # DISCREPANCY 1: settled_after_failure
        {"event_id":"d1a","event_type":"payment_initiated","transaction_id":"txn-disc-1","merchant_id":"merchant_2","merchant_name":"FreshBasket","amount":5000,"currency":"INR","timestamp":"2026-01-01T11:00:00+00:00"},
        {"event_id":"d1b","event_type":"payment_failed","transaction_id":"txn-disc-1","merchant_id":"merchant_2","merchant_name":"FreshBasket","amount":5000,"currency":"INR","timestamp":"2026-01-01T11:05:00+00:00"},
        {"event_id":"d1c","event_type":"settled","transaction_id":"txn-disc-1","merchant_id":"merchant_2","merchant_name":"FreshBasket","amount":5000,"currency":"INR","timestamp":"2026-01-01T13:00:00+00:00"},
        # DISCREPANCY 2: processed_not_settled
        {"event_id":"d2a","event_type":"payment_initiated","transaction_id":"txn-disc-2","merchant_id":"merchant_3","merchant_name":"UrbanEats","amount":3000,"currency":"INR","timestamp":"2026-01-01T09:00:00+00:00"},
        {"event_id":"d2b","event_type":"payment_processed","transaction_id":"txn-disc-2","merchant_id":"merchant_3","merchant_name":"UrbanEats","amount":3000,"currency":"INR","timestamp":"2026-01-01T09:05:00+00:00"},
        # DISCREPANCY 3: stale_initiated
        {"event_id":"d3a","event_type":"payment_initiated","transaction_id":"txn-disc-3","merchant_id":"merchant_1","merchant_name":"QuickMart","amount":2000,"currency":"INR","timestamp":"2026-01-01T08:00:00+00:00"},
    ]
    for e in events:
        client.post("/events", json=e)


class TestReconciliationSummary:

    def test_summary_returns_correct_totals(self, client):
        seed_discrepancy_scenarios(client)
        resp = client.get("/reconciliation/summary")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_transactions"] == 4
        assert "by_merchant" in body
        assert "by_status" in body
        assert "by_date" in body

    def test_summary_has_three_merchants(self, client):
        seed_discrepancy_scenarios(client)
        body = client.get("/reconciliation/summary").json()
        merchant_ids = [m["merchant_id"] for m in body["by_merchant"]]
        assert "merchant_1" in merchant_ids
        assert "merchant_2" in merchant_ids
        assert "merchant_3" in merchant_ids

    def test_summary_settlement_rate(self, client):
        seed_discrepancy_scenarios(client)
        body = client.get("/reconciliation/summary").json()
        qm = next(m for m in body["by_merchant"] if m["merchant_id"] == "merchant_1")
        # QuickMart has 2 transactions: 1 settled, 1 stale_initiated
        assert qm["settled_count"] == 1
        assert qm["total_transactions"] == 2

    def test_summary_filter_by_merchant(self, client):
        seed_discrepancy_scenarios(client)
        body = client.get("/reconciliation/summary?merchant_id=merchant_2").json()
        assert body["total_transactions"] == 1
        assert len(body["by_merchant"]) == 1
        assert body["by_merchant"][0]["merchant_id"] == "merchant_2"

    def test_summary_by_status_contains_expected_statuses(self, client):
        seed_discrepancy_scenarios(client)
        body = client.get("/reconciliation/summary").json()
        statuses = [s["status"] for s in body["by_status"]]
        assert "settled" in statuses
        assert "processed" in statuses
        assert "initiated" in statuses


class TestReconciliationDiscrepancies:

    def test_returns_all_three_discrepancy_types(self, client):
        seed_discrepancy_scenarios(client)
        resp = client.get("/reconciliation/discrepancies")
        assert resp.status_code == 200
        body = resp.json()
        types = {d["discrepancy_type"] for d in body["discrepancies"]}
        assert "settled_after_failure" in types
        assert "processed_not_settled" in types
        assert "stale_initiated" in types

    def test_settled_after_failure_detected(self, client):
        seed_discrepancy_scenarios(client)
        body = client.get("/reconciliation/discrepancies").json()
        saf = [d for d in body["discrepancies"] if d["discrepancy_type"] == "settled_after_failure"]
        assert len(saf) == 1
        assert saf[0]["transaction_id"] == "txn-disc-1"
        assert saf[0]["merchant_name"] == "FreshBasket"

    def test_processed_not_settled_detected(self, client):
        seed_discrepancy_scenarios(client)
        body = client.get("/reconciliation/discrepancies").json()
        pns = [d for d in body["discrepancies"] if d["discrepancy_type"] == "processed_not_settled"]
        assert len(pns) == 1
        assert pns[0]["transaction_id"] == "txn-disc-2"

    def test_stale_initiated_detected(self, client):
        seed_discrepancy_scenarios(client)
        body = client.get("/reconciliation/discrepancies").json()
        si = [d for d in body["discrepancies"] if d["discrepancy_type"] == "stale_initiated"]
        assert len(si) == 1
        assert si[0]["transaction_id"] == "txn-disc-3"

    def test_happy_path_transaction_not_flagged(self, client):
        seed_discrepancy_scenarios(client)
        body = client.get("/reconciliation/discrepancies").json()
        txn_ids = [d["transaction_id"] for d in body["discrepancies"]]
        assert "txn-happy" not in txn_ids

    def test_filter_by_discrepancy_type(self, client):
        seed_discrepancy_scenarios(client)
        resp = client.get("/reconciliation/discrepancies?discrepancy_type=settled_after_failure")
        body = resp.json()
        assert body["total_discrepancies"] == 1
        assert body["discrepancies"][0]["discrepancy_type"] == "settled_after_failure"

    def test_filter_by_merchant_id(self, client):
        seed_discrepancy_scenarios(client)
        body = client.get("/reconciliation/discrepancies?merchant_id=merchant_2").json()
        assert all(d["merchant_id"] == "merchant_2" for d in body["discrepancies"])

    def test_breakdown_counts_correct(self, client):
        seed_discrepancy_scenarios(client)
        body = client.get("/reconciliation/discrepancies").json()
        breakdown = body["breakdown"]
        assert breakdown["settled_after_failure"] == 1
        assert breakdown["processed_not_settled"] == 1
        assert breakdown["stale_initiated"] == 1
