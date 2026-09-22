"""Flask API Gateway application factory.

Routes authenticated, rate-limited traffic to the users-service and
posts-service FastAPI microservices, with JWT auth, Redis-backed rate
limiting, circuit-breaker-protected proxying, correlation-ID propagation,
Prometheus metrics, and OpenTelemetry tracing exported to Jaeger over OTLP.

Logging note: structured JSON request logs (see JsonLogFormatter below) are
this project's deliberate substitute for a full ELK stack, which is out of
scope for a portfolio-sized deployment — the JSON lines are still ready to
ship to any log aggregator that can tail stdout.
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid

from flask import Flask, g, jsonify, request
from flask_cors import CORS
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from core.db import init_db
from routes.auth import auth_bp
from routes.health import health_bp
from routes.proxy import proxy_bp

REQUEST_COUNT = Counter(
    "gateway_requests_total", "Total requests handled by the gateway", ["method", "path", "status"]
)
REQUEST_LATENCY = Histogram(
    "gateway_request_latency_seconds", "Request latency in seconds", ["method", "path"]
)


class JsonLogFormatter(logging.Formatter):
    """Emits one JSON object per log line with correlation_id/method/path/status/latency_ms."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }
        for field in ("correlation_id", "method", "path", "status", "latency_ms"):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def _configure_logging() -> logging.Logger:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(os.getenv("LOG_LEVEL", "INFO"))
    return logging.getLogger("gateway")


def _configure_tracing(app: Flask) -> None:
    """Best-effort OpenTelemetry setup. Must never prevent the app from starting."""
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.flask import FlaskInstrumentor
        from opentelemetry.instrumentation.requests import RequestsInstrumentor
        from opentelemetry.sdk.resources import SERVICE_NAME, Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318/v1/traces")
        resource = Resource.create({SERVICE_NAME: os.getenv("OTEL_SERVICE_NAME", "api-gateway")})
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

        FlaskInstrumentor().instrument_app(app)
        RequestsInstrumentor().instrument()
    except Exception:  # noqa: BLE001 - tracing must be optional, never fatal
        logging.getLogger("gateway").warning(
            "OpenTelemetry tracing setup failed; continuing without tracing", exc_info=True
        )


def create_app() -> Flask:
    app = Flask(__name__)
    logger = _configure_logging()

    cors_origins = os.getenv("CORS_ORIGINS", "*")
    CORS(app, origins=[o.strip() for o in cors_origins.split(",")] if cors_origins != "*" else "*")

    _configure_tracing(app)

    init_db()

    app.register_blueprint(health_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(proxy_bp)

    @app.before_request
    def _start_timer_and_correlation_id():
        g.correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        g.start_time = time.monotonic()

    @app.after_request
    def _log_and_measure(response):
        latency_ms = round((time.monotonic() - g.get("start_time", time.monotonic())) * 1000, 2)
        endpoint_label = request.url_rule.rule if request.url_rule else request.path

        REQUEST_COUNT.labels(method=request.method, path=endpoint_label, status=response.status_code).inc()
        REQUEST_LATENCY.labels(method=request.method, path=endpoint_label).observe(latency_ms / 1000)

        logger.info(
            "%s %s -> %s",
            request.method,
            request.path,
            response.status_code,
            extra={
                "correlation_id": g.get("correlation_id"),
                "method": request.method,
                "path": request.path,
                "status": response.status_code,
                "latency_ms": latency_ms,
            },
        )

        response.headers["X-Correlation-ID"] = g.get("correlation_id", "")
        return response

    @app.route("/metrics")
    def metrics():
        return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(500)
    def internal_error(_error):
        return jsonify({"error": "Internal server error"}), 500

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")), debug=os.getenv("FLASK_ENV") == "development")
