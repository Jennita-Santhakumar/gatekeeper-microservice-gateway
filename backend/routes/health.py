"""Health-check routes. Both are unauthenticated so dashboards/orchestrators can poll them."""

from __future__ import annotations

import requests
from flask import Blueprint, jsonify

from core.circuit import POSTS_SERVICE_URL, USERS_SERVICE_URL

health_bp = Blueprint("health", __name__)

_HEALTH_CHECK_TIMEOUT_SECONDS = 2


@health_bp.get("/health")
def health():
    """Gateway self-check — no downstream calls, just confirms the process is up."""
    return jsonify({"status": "ok", "service": "api-gateway"}), 200


def _check_service(name: str, base_url: str) -> dict:
    try:
        resp = requests.get(f"{base_url}/health", timeout=_HEALTH_CHECK_TIMEOUT_SECONDS)
        return {
            "status": "ok" if resp.ok else "degraded",
            "http_status": resp.status_code,
        }
    except requests.exceptions.RequestException as exc:
        return {"status": "unreachable", "error": str(exc)}


@health_bp.get("/services/health")
def services_health():
    """Aggregated live health of the gateway plus its downstream services."""
    services = {
        "users-service": _check_service("users-service", USERS_SERVICE_URL),
        "posts-service": _check_service("posts-service", POSTS_SERVICE_URL),
    }
    return jsonify({"gateway": "ok", "services": services}), 200
