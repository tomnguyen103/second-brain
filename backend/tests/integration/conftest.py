"""Integration test fixtures: db_session (transaction-rolled-back) + FastAPI test client."""
from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

# Skip all integration tests when no DB URL is set
_DB_URL = os.getenv("SECOND_BRAIN_TEST_DATABASE_URL")


@pytest.fixture(scope="session")
def db_engine():
    if not _DB_URL:
        pytest.skip("SECOND_BRAIN_TEST_DATABASE_URL not set")
    engine = create_engine(_DB_URL, pool_pre_ping=True, future=True)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    """Each test gets a transaction that is rolled back on teardown."""
    conn = db_engine.connect()
    txn = conn.begin()
    session = Session(bind=conn)
    yield session
    session.close()
    txn.rollback()
    conn.close()


@pytest.fixture
def client(db_session, fake_embedder, test_settings):
    """FastAPI TestClient with DB/embedder/settings overridden to test fixtures."""
    from fastapi.testclient import TestClient
    from app.main import app
    from app import deps

    app.dependency_overrides[deps.get_db] = lambda: (yield db_session)
    app.dependency_overrides[deps.get_embedder] = lambda: fake_embedder
    app.dependency_overrides[deps.get_settings] = lambda: test_settings

    with TestClient(app) as c:
        c.headers.update({"Authorization": "Bearer test-api-token"})
        yield c

    app.dependency_overrides.clear()
