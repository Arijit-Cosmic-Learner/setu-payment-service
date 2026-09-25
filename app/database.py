"""
database.py
-----------
Sets up the SQLAlchemy database engine and session.

Key concepts:
- engine: the connection to the database (SQLite locally, PostgreSQL on Render)
- SessionLocal: a factory that creates DB sessions (think of it as opening a conversation with the DB)
- Base: the parent class all our ORM models will inherit from
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import settings

# -------------------------------------------------------
# Engine
# -------------------------------------------------------
# SQLite needs check_same_thread=False because FastAPI handles
# requests on multiple threads. For PostgreSQL this is ignored.
connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=settings.DEBUG,  # logs every SQL query when DEBUG=true
)

# -------------------------------------------------------
# Session Factory
# -------------------------------------------------------
# Each API request gets its own session (its own conversation with the DB).
# autocommit=False: we manually control when to save changes.
# autoflush=False: we control when to sync Python objects to DB.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# -------------------------------------------------------
# Base Class
# -------------------------------------------------------
# All ORM models inherit from this Base.
# SQLAlchemy uses it to track all tables.
class Base(DeclarativeBase):
    pass


# -------------------------------------------------------
# Dependency - injected into every FastAPI route
# -------------------------------------------------------
# Opens a DB session, gives it to the route, then closes it.
# try/finally ensures the session is ALWAYS closed, even on errors.
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
