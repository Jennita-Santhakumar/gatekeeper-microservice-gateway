"""Circuit-breaker-protected HTTP client for calling downstream microservices.

Wraps `requests` calls to users-service and posts-service with the
`circuitbreaker` package so repeated failures against a downstream service
trip the breaker and fail fast (raising `CircuitBreakerError`) instead of
piling up slow/hanging requests against a service that's already down.
"""

from __future__ import annotations

import os
from typing import Any

import requests
from circuitbreaker import circuit

USERS_SERVICE_URL = os.getenv("USERS_SERVICE_URL", "http://localhost:8101")
POSTS_SERVICE_URL = os.getenv("POSTS_SERVICE_URL", "http://localhost:8102")

CIRCUIT_FAILURE_THRESHOLD = int(os.getenv("CIRCUIT_FAILURE_THRESHOLD", "5"))
CIRCUIT_RECOVERY_TIMEOUT = int(os.getenv("CIRCUIT_RECOVERY_TIMEOUT", "30"))
DOWNSTREAM_TIMEOUT_SECONDS = float(os.getenv("DOWNSTREAM_TIMEOUT_SECONDS", "5"))

SERVICE_BASE_URLS = {
    "users": USERS_SERVICE_URL,
    "posts": POSTS_SERVICE_URL,
}

_METHOD_MAP = {
    "GET": requests.get,
    "POST": requests.post,
    "PUT": requests.put,
    "PATCH": requests.patch,
    "DELETE": requests.delete,
}


class UnknownServiceError(Exception):
    """Raised when `service` doesn't match a known downstream service name."""


@circuit(
    failure_threshold=CIRCUIT_FAILURE_THRESHOLD,
    recovery_timeout=CIRCUIT_RECOVERY_TIMEOUT,
    expected_exception=requests.exceptions.RequestException,
)
def _do_request(
    method: str,
    url: str,
    headers: dict[str, str] | None,
    json_body: Any,
    params: dict[str, Any] | None,
) -> requests.Response:
    fn = _METHOD_MAP.get(method.upper())
    if fn is None:
        raise ValueError(f"Unsupported HTTP method: {method}")
    return fn(
        url,
        headers=headers,
        json=json_body,
        params=params,
        timeout=DOWNSTREAM_TIMEOUT_SECONDS,
    )


def proxy_request(
    service: str,
    method: str,
    path: str,
    headers: dict[str, str] | None = None,
    json_body: Any = None,
    params: dict[str, Any] | None = None,
) -> requests.Response:
    """Forward a request to the given downstream `service` ("users" or "posts").

    `path` should not include a leading service prefix, e.g. "/1" or "/health".
    Raises `UnknownServiceError` for an unrecognized service name, and
    `circuitbreaker.CircuitBreakerError` when the breaker is open, or a
    `requests.exceptions.RequestException` subclass on transport failure.
    """
    base_url = SERVICE_BASE_URLS.get(service)
    if base_url is None:
        raise UnknownServiceError(f"Unknown downstream service: {service}")

    if not path.startswith("/"):
        path = f"/{path}"
    url = f"{base_url}{path}"

    return _do_request(method, url, headers, json_body, params)
