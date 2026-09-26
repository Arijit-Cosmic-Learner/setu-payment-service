"""
main.py
-------
The entry point of the FastAPI application.

This file:
1. Creates the FastAPI app instance
2. Registers all routers (events, transactions, reconciliation)
3. Adds a visual interactive dashboard UI at /
4. Adds a branded custom ReDoc documentation portal at /redoc
5. Adds health check endpoints
6. Configures OpenAPI documentation metadata
"""

from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from app.config import settings
from app.routers import events, transactions, reconciliation
from app.redoc_custom import get_custom_redoc_html

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
    payment_initiated -> payment_processed -> settled   (happy path)
    payment_initiated -> payment_failed                 (failure path)
    ```
    """,
    contact={
        "name": "Arijit Mitra",
        "url": "https://github.com/Arijit-Cosmic-Learner/setu-payment-service",
    },
    docs_url="/docs",       # Swagger UI (untouched)
    redoc_url=None,         # Managed by custom branded route below
)

# ===========================================================
# CORS Middleware
# ===========================================================
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

# Locate templates directory relative to this file
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
INDEX_HTML_PATH = TEMPLATES_DIR / "index.html"


# ===========================================================
# Visual Dashboard & Landing Page
# ===========================================================
@app.get("/", response_class=HTMLResponse, tags=["Dashboard"], summary="Visual Interactive Portal")
def root_portal():
    """
    Serves the visual interactive payment dashboard & documentation portal.
    """
    if INDEX_HTML_PATH.exists():
        return HTMLResponse(content=INDEX_HTML_PATH.read_text(encoding="utf-8"))
    
    return HTMLResponse(content=f"""
    <!DOCTYPE html>
    <html>
      <head><title>{settings.APP_NAME}</title></head>
      <body style="font-family: sans-serif; padding: 2rem; text-align: center;">
        <h1>{settings.APP_NAME} v{settings.APP_VERSION}</h1>
        <p>Service is live and healthy.</p>
        <p><a href="/docs">Swagger UI (/docs)</a> | <a href="/redoc">ReDoc (/redoc)</a></p>
      </body>
    </html>
    """)


# ===========================================================
# Custom Branded ReDoc UI
# ===========================================================
@app.get("/redoc", response_class=HTMLResponse, tags=["Documentation"], summary="Branded ReDoc Documentation")
def redoc_html():
    """
    Serves the custom styled ReDoc documentation aligned with the Setu theme.
    """
    return HTMLResponse(
        content=get_custom_redoc_html(
            openapi_url=app.openapi_url or "/openapi.json",
            title=f"{settings.APP_NAME} - ReDoc API Documentation",
        )
    )


# ===========================================================
# Health Check (Machine Readable)
# ===========================================================
@app.get("/health", tags=["Health"], summary="Detailed health check")
def health():
    """
    Detailed JSON health status for automated uptime probes and load balancers.
    """
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "redoc": "/redoc",
    }
