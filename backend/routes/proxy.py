"""Authenticated, rate-limited proxy routes to downstream microservices.

`/api/users/<path>` -> users-service, `/api/posts/<path>` -> posts-service.
Each route requires a valid JWT (require_auth), is rate limited, and forwards
Authorization / X-Correlation-ID / X-Forwarded-For headers plus the JSON body
through core.circuit.proxy_request. Circuit-open or downstream connectivity
failures are surfaced as a 503 JSON error rather than propagating a 500.
"""

from __future__ import annotations

import logging

from circuitbreaker import CircuitBreakerError
from flask import Blueprint, g, jsonify, request
from requests.exceptions import RequestException

from core.circuit import UnknownServiceError, proxy_request
from core.rate_limit import rate_limit
from core.security import require_auth

logger = logging.getLogger(__name__)

proxy_bp = Blueprint("proxy", __name__, url_prefix="/api")

_METHODS = ["GET", "POST", "PUT", "DELETE", "PATCH"]


def _forwarded_headers() -> dict[str, str]:
    headers: dict[str, str] = {}
    auth_header = request.headers.get("Authorization")
    if auth_header:
        headers["Authorization"] = auth_header
    correlation_id = getattr(g, "correlation_id", None)
    if correlation_id:
        headers["X-Correlation-ID"] = correlation_id
    if request.remote_addr:
        headers["X-Forwarded-For"] = request.remote_addr
    return headers


def _proxy(service: str, resource: str, endpoint: str = ""):
    # `resource` is the downstream service's own route prefix ("users"/"posts") --
    # e.g. gateway `/api/users/1` forwards to `{USERS_SERVICE_URL}/users/1`, and
    # gateway `/api/users` (no suffix) forwards to `{USERS_SERVICE_URL}/users`.
    # Forwarding bare `/{endpoint}` (dropping the resource prefix) would hit a
    # route that doesn't exist on either downstream service.
    downstream_path = f"/{resource}/{endpoint}" if endpoint else f"/{resource}"
    try:
        upstream = proxy_request(
            service=service,
            method=request.method,
            path=downstream_path,
            headers=_forwarded_headers(),
            json_body=request.get_json(silent=True) if request.is_json else None,
            params=request.args,
        )
    except CircuitBreakerError:
        logger.error("Circuit open for %s-service", service)
        return jsonify({"error": f"{service}-service temporarily unavailable (circuit open)"}), 503
    except RequestException as exc:
        logger.error("Error calling %s-service: %s", service, exc)
        return jsonify({"error": f"{service}-service unavailable"}), 503
    except UnknownServiceError as exc:
        return jsonify({"error": str(exc)}), 404

    try:
        body = upstream.json()
    except ValueError:
        body = {"raw": upstream.text}

    return jsonify(body), upstream.status_code


@proxy_bp.route("/users", methods=_METHODS)
@proxy_bp.route("/users/<path:endpoint>", methods=_METHODS)
@require_auth
@rate_limit(limit=1000, window_seconds=60, scope="users")
def proxy_users(endpoint: str = ""):
    return _proxy("users", "users", endpoint)


@proxy_bp.route("/posts", methods=_METHODS)
@proxy_bp.route("/posts/<path:endpoint>", methods=_METHODS)
@require_auth
@rate_limit(limit=500, window_seconds=60, scope="posts")
def proxy_posts(endpoint: str = ""):
    return _proxy("posts", "posts", endpoint)
