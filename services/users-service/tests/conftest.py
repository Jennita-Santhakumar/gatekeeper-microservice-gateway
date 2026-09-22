"""Shared pytest fixtures for users-service.

Runs against an in-memory SQLite database via a dependency override, so
the full test suite runs locally without Docker/Postgres. This mirrors
the pattern used by other services in this portfolio, which run their
integration suite against a real Postgres service container in CI but
keep the default local run dependency-light.
"""

from __future__ import annotations

import os

os.environ.setdefault("GATEWAY_ORIGIN", "http://localhost:5000")
# Avoid trying to reach a real collector during tests.
os.environ.setdefault("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318/v1/traces")
# Must be set before `app.main` is imported below: the module-level engine in
# app/database.py is built from this env var at import time, and the
# `@app.on_event("startup")` handler runs `Base.metadata.create_all(bind=engine)`
# against that same module-level engine when TestClient enters its context --
# without this, startup tries to reach the real Postgres container and fails.
# A plain in-memory sqlite:// URL would give each new connection/thread its
# own separate empty database (TestClient's portal runs in a worker thread),
# so a temp file is used instead to guarantee one shared database on disk.
import tempfile  # noqa: E402

_startup_db_fd, _startup_db_path = tempfile.mkstemp(suffix=".db")
os.close(_startup_db_fd)
os.environ.setdefault("DATABASE_URL", f"sqlite+pysqlite:///{_startup_db_path}")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def db_session_factory():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    yield TestingSessionLocal
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture()
def client(db_session_factory):
    def override_get_db():
        db = db_session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
