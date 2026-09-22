"""Shared pytest fixtures: an isolated in-memory-DB Flask app + test client,
with fakeredis swapped in for rate limiting so tests don't need a real Redis."""

from __future__ import annotations

import os

import fakeredis
import pytest

os.environ.setdefault("GATEWAY_DB_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318/v1/traces")


@pytest.fixture()
def app():
    # Use a fresh in-memory sqlite DB per test via a shared StaticPool-like URL.
    os.environ["GATEWAY_DB_URL"] = "sqlite://"

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    import core.db as db_module

    db_module.engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    db_module.SessionLocal = sessionmaker(bind=db_module.engine, autoflush=False, autocommit=False, future=True)

    # Patch the SessionLocal reference already imported into routes.auth
    import routes.auth as auth_module

    auth_module.SessionLocal = db_module.SessionLocal

    from app import create_app
    from core.rate_limit import set_redis_client

    set_redis_client(fakeredis.FakeStrictRedis(decode_responses=True))

    flask_app = create_app()
    flask_app.config.update(TESTING=True)
    return flask_app


@pytest.fixture()
def client(app):
    return app.test_client()
