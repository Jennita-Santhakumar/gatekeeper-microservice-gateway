"""Database engine/session setup for users-service.

DATABASE_URL defaults to the local-dev docker-compose port mapping
(external 5442 -> users-postgres:5432 inside the compose network). In
compose, override DATABASE_URL to point at the service hostname, e.g.
postgresql+psycopg://users:users@users-postgres:5432/users_db
"""

from __future__ import annotations

import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://users:users@localhost:5442/users_db",
)

# pool_pre_ping guards against stale connections after DB restarts/idles.
engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator:
    """FastAPI dependency that yields a request-scoped DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# NOTE: Base.metadata.create_all(bind=engine) is called on app startup in
# main.py. This is a deliberate simplification instead of a full Alembic
# migration setup -- appropriate for this project's scope (a single simple
# `users` table, no schema evolution across environments). A production
# service handling real migrations would use Alembic instead.
