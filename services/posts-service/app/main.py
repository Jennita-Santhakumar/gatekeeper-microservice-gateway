import logging
import os

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import Base, engine, get_db
from app.models import Post
from app.schemas import HealthStatus, PostCreate, PostList, PostOut

logger = logging.getLogger("posts-service")

OTEL_EXPORTER_OTLP_ENDPOINT = os.getenv(
    "OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318/v1/traces"
)


def _setup_tracing() -> None:
    """Configure OpenTelemetry tracing, exporting via OTLP/HTTP to Jaeger.

    This must never crash app startup if the collector is unreachable: the
    OTLP HTTP exporter batches spans in the background and simply drops them
    (with a logged warning) on export failure, so we don't need to do
    anything special here besides catching setup errors defensively.
    """
    try:
        resource = Resource.create({SERVICE_NAME: "posts-service"})
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=OTEL_EXPORTER_OTLP_ENDPOINT)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
    except Exception:  # pragma: no cover - defensive, must never block startup
        logger.warning("OpenTelemetry tracing setup failed; continuing without it", exc_info=True)


_setup_tracing()

app = FastAPI(title="posts-service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("GATEWAY_ORIGIN", "http://localhost:8080")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

try:
    FastAPIInstrumentor.instrument_app(app)
    SQLAlchemyInstrumentor().instrument(engine=engine)
except Exception:  # pragma: no cover - defensive, must never block startup
    logger.warning("OpenTelemetry instrumentation failed; continuing without it", exc_info=True)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)


@app.post("/posts", response_model=PostOut, status_code=201)
def create_post(payload: PostCreate, db: Session = Depends(get_db)) -> Post:
    post = Post(user_id=payload.user_id, title=payload.title, content=payload.content)
    db.add(post)
    db.commit()
    db.refresh(post)
    return post


@app.get("/posts/{post_id}", response_model=PostOut)
def get_post(post_id: int, db: Session = Depends(get_db)) -> Post:
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    return post


@app.get("/posts", response_model=PostList)
def list_posts(
    user_id: int | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> PostList:
    query = db.query(Post)
    if user_id is not None:
        query = query.filter(Post.user_id == user_id)

    total = query.count()
    items = (
        query.order_by(Post.id.asc()).offset(offset).limit(limit).all()
    )
    return PostList(items=items, limit=limit, offset=offset, total=total)


@app.delete("/posts/{post_id}", status_code=204)
def delete_post(post_id: int, db: Session = Depends(get_db)) -> None:
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    db.delete(post)
    db.commit()


@app.get("/health", response_model=HealthStatus)
def health(db: Session = Depends(get_db)) -> HealthStatus:
    try:
        db.execute(text("SELECT 1"))
        return HealthStatus(status="ok", database="ok")
    except Exception:
        logger.warning("Health check DB connectivity failed", exc_info=True)
        return HealthStatus(status="degraded", database="unreachable")
