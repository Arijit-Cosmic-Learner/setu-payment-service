# 🏦 Setu Payment Lifecycle & Reconciliation Service

## 1. Executive Summary

**One-Liner:** 
A robust, highly scalable backend service designed to ingest payment lifecycle events, track dynamic transaction state machines, and automatically detect financial discrepancies through an advanced reconciliation engine.

**Overview:**
In modern fintech ecosystems, payment processing is rarely a single synchronous action. A single customer transaction involves multiple asynchronous hops between banks, gateways, and merchants. This project serves as the centralized source of truth for these events. It exposes a RESTful API to safely ingest continuous streams of payment data, reconstructs the journey of every transaction, and surfaces real-time financial analytics and anomalies.

---

## 2. Problem Statement & Engineering Challenges

Payment gateways and financial aggregators face several critical engineering challenges when handling distributed payment events at scale:

1.  **Network Unreliability & Duplicate Data:** Network timeouts frequently cause payment partners to retry sending the same event webhook multiple times. Without strict **idempotency**, a system might process the same payment twice, leading to catastrophic double-credits.
2.  **Fragmented Transaction States:** Events like `payment_initiated`, `payment_processed`, and `settled` arrive at different times (often days apart). Tracking the exact current state of a payment requires intelligently linking these fragmented events into a single, cohesive state machine.
3.  **The "Black Hole" of Settlement (Reconciliation):** The most critical challenge for merchants is ensuring that a payment marked as "Successful" by the gateway actually results in money being deposited into their bank account (Settled). Manually finding transactions where money is "stuck" or where fraudulent settlements occur is virtually impossible at high volumes. 

**The Solution:**
This service was built specifically to solve these real-world fintech challenges. It guarantees safe, idempotent event ingestion, automatically derives the master state of every transaction, and features a purpose-built SQL reconciliation engine that flags impossible or stuck financial states before they impact merchant payouts.

---

## 3. System Architecture & Tech Stack

To ensure the system is production-minded, deployable, and highly efficient, the architecture was designed around modern, lightweight, and scalable technologies.

*   **Backend Framework:** **FastAPI (Python)** — Chosen for its high performance, native async support, and auto-generated OpenAPI schemas.
*   **Database:** **Supabase (PostgreSQL via SQLAlchemy)** — A serverless remote persistent database with enterprise-grade Postgres capabilities to handle high-throughput financial data safely.
*   **Deployment:** **Vercel** — API is deployed as a serverless function ensuring scaling from zero to thousands of concurrent requests instantly.
*   **Documentation & UI:** **HTML5, Vanilla CSS, and ReDoc** — Custom branded developer portal and visual dashboards.

### Core Architectural Principles

*   **Event-Sourcing & State Machine Derivation:** We treat the `events` table as an immutable ledger. When events arrive, they are appended, and the system dynamically calculates the transaction's master state.
*   **Bulletproof Idempotency:** Using database primary key constraints on `event_id`, duplicates are swallowed gracefully returning a `200 OK` (with `already_processed` status), ensuring financial data is never corrupted by network retries.
*   **SQL-Driven Reconciliation Engine:** Financial aggregations and anomaly detection rules are pushed down directly to the Supabase Postgres engine using optimized `GROUP BY` and `CASE WHEN` queries, guaranteeing lightning-fast metrics across millions of rows.

---

## 4. Live URLs & Developer Experience (DX)

A significant focus was placed on Developer Experience (DX) and visual tooling to ensure the API is instantly usable by frontend engineers and integration partners.

*   **🌐 Base API URL:** `https://setu-payment-service.vercel.app`
*   **🖥️ Visual Dashboard:** [https://setu-payment-service.vercel.app/](https://setu-payment-service.vercel.app/)
*   **📚 Branded Developer Guide (ReDoc):** [https://setu-payment-service.vercel.app/redoc](https://setu-payment-service.vercel.app/redoc)
*   **⚙️ Interactive API Explorer (Swagger):** [https://setu-payment-service.vercel.app/docs](https://setu-payment-service.vercel.app/docs)

---

## 5. API Endpoint Reference

| Method | Endpoint | Domain | Purpose | Key Features |
| :--- | :--- | :--- | :--- | :--- |
| **`POST`** | `/events` | **Ingestion** | Ingest a raw payment lifecycle event. | **Idempotent** (Duplicates return `already_processed`). |
| **`GET`** | `/events` | **Retrieval** | Fetch a paginated ledger of all raw events. | Filterable by: `event_type`, `transaction_id`. |
| **`GET`** | `/transactions` | **Retrieval** | Fetch a paginated list of transactions & master status. | Filterable by `merchant_id`, `status`, `date`. |
| **`GET`** | `/transactions/{id}` | **Retrieval** | Fetch granular details of a single transaction. | Returns the complete chronological event audit trail. |
| **`GET`** | `/reconciliation/summary` | **Recon** | Real-time SQL-aggregated financial summary. | Grouped by merchant (settlement rates), status, date. |
| **`GET`** | `/reconciliation/discrepancies` | **Recon** | Anomaly engine. Flags transactions in stuck states. | Detects impossible/stuck financial edge-cases. |

---

## 6. Discrepancy Detection Rules

The anomaly detection engine evaluates the derived state of a transaction against specific business rules to flag "stuck" financial states.

| Discrepancy Type | Detection Condition | Real-World Impact |
| :--- | :--- | :--- |
| **`settled_after_failure`** | `payment_status` == failed AND `settlement_status` == settled | **High Severity.** Impossible state. Indicates severe system desync, potential fraud, or double-credit bug. |
| **`processed_not_settled`** | `payment_status` == processed AND `settlement_status` == pending | **Medium Severity.** Customer paid successfully, but merchant hasn't received funds. Money is stuck in network. |
| **`stale_initiated`** | `status` == initiated AND (Only 1 event exists) | **Low/Medium Severity.** Initiated payment never progressed. Normal drop-off or webhook failure. |

---

## 7. Assumptions & Tradeoffs

To design a system that is functional for a 3-day assignment but signals a production-grade enterprise mindset, the following assumptions and technical tradeoffs were made:

### Tradeoffs
*   **Synchronous vs. Asynchronous Ingestion:** For this assignment, the `POST /events` endpoint writes directly to the database synchronously. **Tradeoff:** At enterprise scale (millions of events per minute), this would bottleneck the database. In a real Setu environment, events would be pushed to a message broker (like Kafka or RabbitMQ) and processed into the database asynchronously via background workers.
*   **Real-time SQL vs. Materialized Views:** The reconciliation summary currently runs live SQL `GROUP BY` queries on the transactions table. **Tradeoff:** While blazing fast on a dataset of this size, this becomes computationally expensive at massive scale. In production, I would utilize PostgreSQL Materialized Views or run cron jobs to pre-aggregate these financial totals on a nightly basis.

### Assumptions
*   **Event Ordering:** I assumed that events might arrive out of order (e.g., a `settled` webhook arriving before `processed` due to network delays). The state machine was explicitly designed to handle this gracefully without crashing or entering a corrupted state.
*   **Idempotency Key:** I assumed the `event_id` provided by the gateway is a true unique identifier. Our idempotency engine completely relies on this being unique per network attempt.

---

## 8. Local Setup Instructions

Want to run the service locally? Follow these steps:

1. **Clone the repository:**
   ```bash
   git clone <YOUR-GITHUB-URL>
   cd setu-payment-service
   ```
2. **Set up Virtual Environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
4. **Environment Variables:**
   Create a `.env` file at the root of the project with your Supabase Postgres connection string:
   ```env
   DATABASE_URL="postgresql://postgres:[YOUR-PASSWORD]@db.[YOUR-SUPABASE-REF].supabase.co:5432/postgres"
   ```
5. **Run the Application:**
   ```bash
   uvicorn app.main:app --reload
   ```
   The API will be live at `http://localhost:8000`.

---

## 8. Postman Testing Guide

To validate the core business logic, you can utilize the complete Postman collection that handles the Happy Path, Failure Path, Idempotency testing, and Anomaly Simulation.

*Note: You can attach the exported Postman collection JSON file here, or provide a link to the shared workspace.*

---

*I used an AI assistant (Antigravity/Claude) as a pair-programmer for architectural feedback and documentation generation. All code logic, state machine design, and edge-case handling were directed and validated by me.*
