"""Shared pytest fixtures for the database test suite.

Uses an in-memory SQLite database (via StaticPool, so all connections in
a test share the same in-memory DB) instead of the real .db file, keeping
tests fast and fully isolated from development data.
"""

from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.models import execution_log, note, workflow, workflow_step  # noqa: F401


@pytest.fixture()
def db_session():
    """Yield a fresh, isolated database session backed by an in-memory DB."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(bind=engine)

    TestingSessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
    )

    session: Session = TestingSessionLocal()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def workflow_session_factory(db_session):
    """Return a session_scope-compatible factory for WorkflowService tests."""

    @contextmanager
    def _session_factory():
        yield db_session

    return _session_factory


@pytest.fixture()
def client(db_session):
    """Yield a TestClient using the isolated in-memory database."""

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()