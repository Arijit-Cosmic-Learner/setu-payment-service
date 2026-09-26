"""
tests/conftest.py
-----------------
Shared pytest fixtures.

THE FIX (compared to earlier version):
SQLite in-memory databases are connection-scoped by default.
When using ":memory:", each new connection gets its own empty database.
So if the test creates tables on connection A but the app routes use connection B,
the tables don't exist on B — hence "no such table".

SOLUTION: Use a named in-memory URI with "check_same_thread=False" AND
share the same connection across the entire test by using a single
engine + session that we inject via dependency_overrides.
We use "sqlite:///file::memory:?cache=shared&uri=true" which lets
multiple connections share the same in-memory database.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import Base, get_db

# Shared in-memory SQLite - all connections see the same data
SQLALCHEMY_TEST_URL = "sqlite:///file::memory:?cache=shared&uri=true"

engine = create_engine(
    SQLALCHEMY_TEST_URL,
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def reset_db():
    """
    Runs before and after EVERY test automatically (autouse=True).
    Creates all tables before test, drops all tables after.
    This guarantees each test starts with a clean empty database.
    """
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db(reset_db):
    """Provides a database session for tests that need direct DB access."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(reset_db):
    """
    FastAPI TestClient wired to the test database.
    dependency_overrides replaces get_db (real DB) with our test DB session.
    """
    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# -------------------------------------------------------
# Reusable sample event payloads
# -------------------------------------------------------
@pytest.fixture
def sample_event():
    """A valid payment_initiated event."""
    return {
        "event_id": "test-evt-001",
        "event_type": "payment_initiated",
        "transaction_id": "test-txn-001",
        "merchant_id": "merchant_1",
        "merchant_name": "QuickMart",
        "amount": 5000.00,
        "currency": "INR",
        "timestamp": "2026-01-10T10:00:00+00:00",
    }


@pytest.fixture
def full_transaction_events():
    """Events for a complete happy-path: initiated -> processed -> settled."""
    return [
        {"event_id": "e-init", "event_type": "payment_initiated",  "transaction_id": "txn-full", "merchant_id": "merchant_1", "merchant_name": "QuickMart", "amount": 9999, "currency": "INR", "timestamp": "2026-01-10T10:00:00+00:00"},
        {"event_id": "e-proc", "event_type": "payment_processed",  "transaction_id": "txn-full", "merchant_id": "merchant_1", "merchant_name": "QuickMart", "amount": 9999, "currency": "INR", "timestamp": "2026-01-10T10:05:00+00:00"},
        {"event_id": "e-setl", "event_type": "settled",            "transaction_id": "txn-full", "merchant_id": "merchant_1", "merchant_name": "QuickMart", "amount": 9999, "currency": "INR", "timestamp": "2026-01-10T12:00:00+00:00"},
    ]
