# Setu Payment Service

A robust, idempotent, and highly scalable Payment Reconciliation Service built with **FastAPI**, **SQLAlchemy**, **PostgreSQL**, and deployed on a serverless architecture (**Vercel + Supabase**).

## Live API URL
**Base URL:** `https://setu-payment-service.vercel.app`

*(Note: The root path `/` is intentionally left blank. Please use the API endpoints below).*

## 🚀 Key Features & Architectural Decisions

### 1. True Idempotency
Payment systems require strict idempotency to prevent double-charging or duplicate event processing. 
- The `events` table enforces a `UNIQUE(event_id)` constraint.
- The `event_service` intercepts HTTP `POST` requests and gracefully handles `IntegrityError` exceptions. 
- If a client retries sending the exact same `event_id`, the API safely ignores the duplicate and returns a `200 OK` (or `201` on first creation), ensuring external webhooks never get stuck in a failure loop.

### 2. State Machine Enforcement
Transactions transition through strict states: `initiated` -> `processed` -> `settled` (or `failed`).
- The system prevents invalid transitions (e.g., you cannot go from `settled` back to `initiated`).
- If an out-of-order event arrives (e.g., `payment_settled` arrives before `payment_initiated` due to network lag), the system intelligently logs the event but does not corrupt the transaction state, allowing reconciliation to flag it.

### 3. High-Performance SQL Reconciliation
Instead of loading thousands of rows into Python memory to find discrepancies (which scales poorly), the reconciliation engine pushes the heavy lifting to PostgreSQL using **SQL Aggregations**.
- Uses `CASE WHEN` and `GROUP BY` to dynamically detect `stale_initiated`, `processed_not_settled`, and `settled_after_failure` anomalies in a single, lightning-fast database query.
- This approach handles 10,000+ events in milliseconds.

### 4. Serverless & Decoupled Architecture
- **Compute:** Vercel Serverless Functions. Stateless, instantly scalable.
- **Database:** Supabase (PostgreSQL). Connection pooling enabled via PgBouncer to prevent connection exhaustion from serverless cold starts.

## 🧪 Running Locally

1. **Clone & Install**
   ```bash
   git clone https://github.com/Arijit-Cosmic-Learner/setu-payment-service.git
   cd setu-payment-service
   python -m venv venv
   source venv/Scripts/activate
   pip install -r requirements.txt
   ```

2. **Database Setup**
   Copy `.env.example` to `.env` and set your local SQLite or Postgres URL.
   ```bash
   alembic upgrade head
   python scripts/seed_data.py
   ```

3. **Run Server**
   ```bash
   fastapi dev app/main.py
   ```

## 📚 API Endpoints

- `POST /events` - Ingest a payment event.
- `GET /events` - List events (supports pagination: `?page=1&size=50` and filtering `?transaction_id=XYZ`).
- `GET /transactions` - List latest transaction states.
- `GET /reconciliation/summary` - Get high-level settlement stats.
- `GET /reconciliation/discrepancies` - Returns flagged anomalies (stale, invalid transitions).

## 📊 Testing
The project includes a robust suite of `pytest` cases testing idempotency, state transitions, and SQL aggregations using an isolated in-memory database.
```bash
pytest
```
