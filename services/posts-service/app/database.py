"""Database engine/session setup for posts-service.

Local dev default points at a docker-compose-mapped port (5443 -> internal 5432)
so this can run against a local Postgres without colliding with other services'
default ports. Inside docker-compose, DATABASE_URL is expected to be overridden
to something like postgresql+psycopg://posts:posts@posts-postgres:5432/posts_db
(service name + internal port).

We call Base.metadata.create_all(bind=engine) on startup instead of wiring up
Alembic migrations. This is a deliberate simplification matching the scope of
this portfolio project (a small, self-contained microservice demo) rather than
a production schema-migration story.
"""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://posts:posts@localhost:5443/posts_db",
)

# pool_pre_ping guards against stale connections after DB restarts/network blips.
engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
