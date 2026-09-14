import os

# Required settings must exist before `app.config.get_settings()` is ever
# imported (module import time), so we set them here, at the very top of
# the test session, before any `app.*` import happens.
os.environ.setdefault("AEMET_API_KEY", "test-key")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("LOG_LEVEL", "WARNING")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.routers.antartida import get_aemet_client


@pytest.fixture()
def db_session():
    """
    A fresh, isolated in-memory SQLite DB per test.

    `poolclass=StaticPool` is required for ':memory:' SQLite: without it,
    SQLAlchemy's pool may hand out a *different* physical connection on a
    later checkout (e.g. because the endpoint runs in FastAPI's worker
    thread), and each new connection to ':memory:' is a brand new, empty
    database -- which looks like "no such table" even though `create_all`
    just ran successfully moments earlier.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


class FakeAemetClient:
    """Stand-in for AemetClient, returning canned readings instead of hitting the network."""

    def __init__(self, readings: list[dict] | None = None):
        self.readings = readings or []
        self.calls: list[tuple[str, str, str]] = []

    def fetch_antartida_readings(self, station_id, start_utc, end_utc):
        self.calls.append((station_id, start_utc.isoformat(), end_utc.isoformat()))
        return self.readings

    def close(self):
        pass


@pytest.fixture()
def fake_aemet_client():
    return FakeAemetClient()


@pytest.fixture()
def client(db_session, fake_aemet_client):
    def override_get_db():
        yield db_session

    def override_get_aemet_client():
        yield fake_aemet_client

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_aemet_client] = override_get_aemet_client
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
