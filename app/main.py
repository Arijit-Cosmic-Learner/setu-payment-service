"""
main.py
-------
The entry point of the FastAPI application.

This file:
1. Creates the FastAPI app instance
2. Registers all routers (events, transactions, reconciliation)
3. Adds a health check endpoint
4. Configures OpenAPI documentation metadata
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import events, transactions, reconciliation

# ===========================================================
# Create FastAPI App
# ===========================================================
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
    ## Setu Payment Service

    A backend service for ingesting payment lifecycle events,
    maintaining transaction state, and surfacing reconciliation insights.

    ### Key Features
    - **Idempotent event ingestion** - safe to retry, duplicates handled gracefully
    - **Transaction tracking** - filter by merchant, status, date range
    - **Reconciliation** - detect discrepancies between payment and settlement state

    ### Event Lifecycle
    ```
    payment_initiated → payment_processed → settled   (happy path)
    payment_initiated → payment_failed               (failure path)
    ```
    """,
    contact={
        "name": "Arijit Mitra",
        "url": "https://github.com/Arijit-Cosmic-Learner/setu-payment-service",
    },
    docs_url="/docs",       # Swagger UI
    redoc_url="/redoc",     # ReDoc UI
)

# ===========================================================
# CORS Middleware
# ===========================================================
# Allows any frontend or Postman to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===========================================================
# Register Routers
# ===========================================================
app.include_router(events.router)
app.include_router(transactions.router)
app.include_router(reconciliation.router)


# ===========================================================
# Health Check
# ===========================================================
@app.get("/", tags=["Health"], summary="Health check")
def root():
    """
    Simple health check endpoint.
    If this returns 200, the service is up and running.
    """
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "healthy",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"], summary="Detailed health check")
def health():
    """Detailed health status."""
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }
