"""SQLAlchemy setup for the gateway's local auth-credentials store.

Deliberate design choice: the gateway owns its own small `gateway_users` table
for authentication credentials (email + password hash), kept separate from
users-service's business-data "users" table. This lets the gateway issue and
validate JWTs independently of users-service's availability. The two records
are correlated by email, not by a shared foreign key/id.

`GATEWAY_DB_URL` controls the backend (defaults to a local SQLite file for
dev; point it at Postgres in docker-compose/production).
"""

from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase, sessionmaker

GATEWAY_DB_URL = os.getenv("GATEWAY_DB_URL", "sqlite:///gateway_auth.db")

_connect_args = {"check_same_thread": False} if GATEWAY_DB_URL.startswith("sqlite") else {}
engine = create_engine(GATEWAY_DB_URL, connect_args=_connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    """Create all tables. Safe to call multiple times (no-op if they exist).

    Gunicorn starts several worker processes, each importing this module and
    calling init_db() independently. Against SQLite, two workers can both
    reflect "table missing" before either issues CREATE TABLE, so the loser
    of that race sees "table already exists" even though checkfirst=True is
    the default -- benign here, so it's swallowed rather than crashing the
    worker's boot.
    """
    from core import models  # noqa: F401  (ensure models are registered on Base)

    try:
        Base.metadata.create_all(bind=engine)
    except OperationalError as exc:
        if "already exists" not in str(exc):
            raise
