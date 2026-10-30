"""Shared pytest fixtures.

Tests use an isolated SQLite database and the real FastAPI app. No external
network calls and no paid AI calls are made — every provider interaction is
either deterministic (local pipeline) or exercised via fixtures/mocks.
"""
from __future__ import annotations

import os
import tempfile

import pytest

# Configure an isolated environment BEFORE importing any app module, so the
# cached settings + engine bind to the test database.
_TMP_DB = os.path.join(tempfile.mkdtemp(prefix="sentinel-test-"), "test.db")
os.environ.update(
    {
        "DATABASE_URL": f"sqlite:///{_TMP_DB}",
        "SECRET_KEY": "test-secret-key",
        "ADMIN_USERNAME": "admin",
        "ADMIN_PASSWORD": "test-admin-pass",
        "ENABLE_SCHEDULER": "false",
        "DEBUG": "false",
        "ENVIRONMENT": "test",
        "RATE_LIMIT_PER_MINUTE": "100000",  # don't rate-limit the test suite
    }
)

from fastapi.testclient import TestClient  # noqa: E402

from app.bootstrap import run_bootstrap  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def _schema():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def clean_db(_schema):
    """Clear all tables and re-seed the admin before each test."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    run_bootstrap(create_schema=False)
    yield


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    # Don't use the lifespan (avoids double-bootstrap + scheduler); schema and
    # seed are handled by clean_db.
    return TestClient(app)


@pytest.fixture
def admin_token(client):
    resp = client.post(
        "/api/auth/token",
        data={"username": "admin", "password": "test-admin-pass"},
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest.fixture
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}
