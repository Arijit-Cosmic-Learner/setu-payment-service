"""
tests/test_transactions.py
--------------------------
Tests for GET /transactions and GET /transactions/{id}
"""

import pytest


def seed_transactions(client):
    """Helper: seed a variety of transactions for filter/pagination tests."""
    events = [
        # merchant_1 - QuickMart: 2 settled, 1 failed
        {"event_id":"qm1a","event_type":"payment_initiated","transaction_id":"qm-txn-1","merchant_id":"merchant_1","merchant_name":"QuickMart","amount":1000,"currency":"INR","timestamp":"2026-01-01T10:00:00+00:00"},
        {"event_id":"qm1b","event_type":"payment_processed","transaction_id":"qm-txn-1","merchant_id":"merchant_1","merchant_name":"QuickMart","amount":1000,"currency":"INR","timestamp":"2026-01-01T10:05:00+00:00"},
        {"event_id":"qm1c","event_type":"settled","transaction_id":"qm-txn-1","merchant_id":"merchant_1","merchant_name":"QuickMart","amount":1000,"currency":"INR","timestamp":"2026-01-01T12:00:00+00:00"},
        {"event_id":"qm2a","event_type":"payment_initiated","transaction_id":"qm-txn-2","merchant_id":"merchant_1","merchant_name":"QuickMart","amount":2000,"currency":"INR","timestamp":"2026-01-02T10:00:00+00:00"},
        {"event_id":"qm2b","event_type":"payment_processed","transaction_id":"qm-txn-2","merchant_id":"merchant_1","merchant_name":"QuickMart","amount":2000,"currency":"INR","timestamp":"2026-01-02T10:05:00+00:00"},
        {"event_id":"qm2c","event_type":"settled","transaction_id":"qm-txn-2","merchant_id":"merchant_1","merchant_name":"QuickMart","amount":2000,"currency":"INR","timestamp":"2026-01-02T12:00:00+00:00"},
        {"event_id":"qm3a","event_type":"payment_initiated","transaction_id":"qm-txn-3","merchant_id":"merchant_1","merchant_name":"QuickMart","amount":3000,"currency":"INR","timestamp":"2026-01-03T10:00:00+00:00"},
        {"event_id":"qm3b","event_type":"payment_failed","transaction_id":"qm-txn-3","merchant_id":"merchant_1","merchant_name":"QuickMart","amount":3000,"currency":"INR","timestamp":"2026-01-03T10:05:00+00:00"},
        # merchant_2 - FreshBasket: 1 settled
        {"event_id":"fb1a","event_type":"payment_initiated","transaction_id":"fb-txn-1","merchant_id":"merchant_2","merchant_name":"FreshBasket","amount":5000,"currency":"INR","timestamp":"2026-01-01T11:00:00+00:00"},
        {"event_id":"fb1b","event_type":"payment_processed","transaction_id":"fb-txn-1","merchant_id":"merchant_2","merchant_name":"FreshBasket","amount":5000,"currency":"INR","timestamp":"2026-01-01T11:05:00+00:00"},
        {"event_id":"fb1c","event_type":"settled","transaction_id":"fb-txn-1","merchant_id":"merchant_2","merchant_name":"FreshBasket","amount":5000,"currency":"INR","timestamp":"2026-01-01T13:00:00+00:00"},
    ]
    for e in events:
        client.post("/events", json=e)


class TestListTransactions:

    def test_returns_all_transactions(self, client):
        seed_transactions(client)
        resp = client.get("/transactions")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 4
        assert len(body["items"]) == 4

    def test_filter_by_merchant_id(self, client):
        seed_transactions(client)
        resp = client.get("/transactions?merchant_id=merchant_1")
        body = resp.json()
        assert body["total"] == 3
        for item in body["items"]:
            assert item["merchant_id"] == "merchant_1"

    def test_filter_by_status_settled(self, client):
        seed_transactions(client)
        resp = client.get("/transactions?status=settled")
        body = resp.json()
        assert body["total"] == 3
        for item in body["items"]:
            assert item["status"] == "settled"

    def test_filter_by_status_failed(self, client):
        seed_transactions(client)
        resp = client.get("/transactions?status=failed")
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["transaction_id"] == "qm-txn-3"

    def test_pagination_page_size(self, client):
        seed_transactions(client)
        resp = client.get("/transactions?page=1&page_size=2")
        body = resp.json()
        assert body["total"] == 4
        assert body["total_pages"] == 2
        assert len(body["items"]) == 2

    def test_pagination_page_2(self, client):
        seed_transactions(client)
        resp = client.get("/transactions?page=2&page_size=2")
        body = resp.json()
        assert len(body["items"]) == 2

    def test_sort_by_amount_asc(self, client):
        seed_transactions(client)
        resp = client.get("/transactions?sort_by=amount&sort_order=asc")
        items = resp.json()["items"]
        amounts = [float(item["amount"]) for item in items]
        assert amounts == sorted(amounts)

    def test_sort_by_amount_desc(self, client):
        seed_transactions(client)
        resp = client.get("/transactions?sort_by=amount&sort_order=desc")
        items = resp.json()["items"]
        amounts = [float(item["amount"]) for item in items]
        assert amounts == sorted(amounts, reverse=True)

    def test_merchant_and_status_combined_filter(self, client):
        seed_transactions(client)
        resp = client.get("/transactions?merchant_id=merchant_1&status=settled")
        body = resp.json()
        assert body["total"] == 2
        for item in body["items"]:
            assert item["merchant_id"] == "merchant_1"
            assert item["status"] == "settled"

    def test_page_size_max_100(self, client):
        resp = client.get("/transactions?page_size=200")
        assert resp.status_code == 422

    def test_empty_result_when_no_match(self, client):
        seed_transactions(client)
        resp = client.get("/transactions?merchant_id=merchant_999")
        body = resp.json()
        assert body["total"] == 0
        assert body["items"] == []


class TestGetTransactionDetail:

    def test_returns_transaction_with_events(self, client, full_transaction_events):
        for e in full_transaction_events:
            client.post("/events", json=e)

        resp = client.get("/transactions/txn-full")
        assert resp.status_code == 200
        body = resp.json()
        assert body["transaction_id"] == "txn-full"
        assert body["merchant_name"] == "QuickMart"
        assert len(body["events"]) == 3

    def test_returns_404_for_unknown_transaction(self, client):
        resp = client.get("/transactions/does-not-exist")
        assert resp.status_code == 404

    def test_merchant_name_included_in_response(self, client, sample_event):
        client.post("/events", json=sample_event)
        resp = client.get(f"/transactions/{sample_event['transaction_id']}")
        assert resp.json()["merchant_name"] == "QuickMart"
