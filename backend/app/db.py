"""
SQLite engine/session setup (Part 2 requirement: cache readings locally so
we don't overload the AEMET source API).

Design notes:
- `check_same_thread=False` is required because FastAPI may serve a request
  on a different thread than the one that created the SQLite connection;
  SQLAlchemy's session-per-request pattern (see `get_db`) keeps this safe.
- We use SQLAlchemy 2.0's typed ORM (`Mapped`/`mapped_column`) instead of
  raw SQL strings, so queries are parametrized by construction (no manual
  string formatting => no SQL injection surface) and readable.
"""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings

settings = get_settings()

is_sqlite = settings.database_url.startswith("sqlite")
is_sqlite_memory = settings.database_url in ("sqlite:///:memory:", "sqlite://")

connect_args = {"check_same_thread": False} if is_sqlite else {}
# ':memory:' SQLite needs StaticPool (a single, persistent connection),
# otherwise a new pooled connection would see a brand new, empty database.
engine_kwargs = {"poolclass": StaticPool} if is_sqlite_memory else {}

engine = create_engine(settings.database_url, connect_args=connect_args, future=True, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    """Create tables if they don't exist yet. Called once on app startup."""
    from app import models_db  # noqa: F401  (ensures models are registered on Base)

    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a DB session, closed after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
