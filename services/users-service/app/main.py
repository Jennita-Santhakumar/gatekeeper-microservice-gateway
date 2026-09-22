"""users-service: a minimal FastAPI microservice owning user registration
and lookup, backed by its own Postgres database. Designed to sit behind
the flask-microservice-api-gateway, which proxies requests to it.
"""

from __future__ import annotations

import logging
import os

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from passlib.context import CryptContext
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.database import Base, engine, get_db
from app.models import User
from app.schemas import HealthStatus, UserCreate, UserList, UserOut

logger = logging.getLogger("users_service")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

app = FastAPI(title="users-service", version="1.0.0")

GATEWAY_ORIGIN = os.environ.get("GATEWAY_ORIGIN", "http://localhost:5000")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[GATEWAY_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _setup_tracing() -> None:
    """Configure OpenTelemetry tracing, exporting via OTLP/HTTP to Jaeger.

    Wrapped so that a missing/unreachable collector never prevents the app
    from starting -- span export failures happen in the background BSP
    worker thread and are swallowed by the exporter, not raised here.
    """
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from opentelemetry.sdk.resources import SERVICE_NAME, Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        service_name = os.environ.get("OTEL_SERVICE_NAME", "users-service")
        otlp_endpoint = os.environ.get(
            "OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318/v1/traces"
        )

        resource = Resource.create({SERVICE_NAME: service_name})
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

        FastAPIInstrumentor.instrument_app(app)
        SQLAlchemyInstrumentor().instrument(engine=engine)
        logger.info("OpenTelemetry tracing configured (endpoint=%s)", otlp_endpoint)
    except Exception:  # pragma: no cover - defensive: tracing must never break the app
        logger.exception("Failed to configure OpenTelemetry tracing; continuing without it")


_setup_tracing()


@app.on_event("startup")
def on_startup() -> None:
    # Deliberate simplification instead of Alembic migrations -- see
    # app/database.py for rationale. Appropriate given this service's
    # single, stable `users` table.
    Base.metadata.create_all(bind=engine)


@app.get("/health", response_model=HealthStatus)
def health(db: Session = Depends(get_db)) -> HealthStatus:
    try:
        db.execute(text("SELECT 1"))
        return HealthStatus(status="ok", database="ok")
    except OperationalError:
        return HealthStatus(status="degraded", database="unreachable")


@app.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: Session = Depends(get_db)) -> User:
    hashed_password = pwd_context.hash(payload.password)
    user = User(
        email=payload.email,
        username=payload.username,
        hashed_password=hashed_password,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        ) from None
    db.refresh(user)
    return user


@app.get("/users/{user_id}", response_model=UserOut)
def get_user(user_id: str, db: Session = Depends(get_db)) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@app.get("/users", response_model=UserList)
def list_users(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> UserList:
    total = db.execute(select(func.count()).select_from(User)).scalar_one()
    rows = (
        db.execute(select(User).order_by(User.created_at).limit(limit).offset(offset))
        .scalars()
        .all()
    )
    return UserList(
        items=[UserOut.model_validate(row) for row in rows],
        limit=limit,
        offset=offset,
        total=total,
    )
