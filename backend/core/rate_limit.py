"""Redis-backed rate limiting for gateway routes.

Uses the classic fixed-window INCR+EXPIRE pattern against Redis. In local dev
the client defaults to localhost:6379; inside docker-compose set REDIS_HOST=redis
(compose network alias) — the external port mapping (e.g. 6390) is irrelevant
here since the gateway talks to Redis over the internal compose network.
"""

from __future__ import annotations

import os
from functools import wraps

import redis
from flask import g, jsonify, request

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))

_redis_client: redis.Redis | None = None


def get_redis_client() -> redis.Redis:
    """Return a lazily-created, module-level Redis client (or a test override)."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis(
            host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True
        )
    return _redis_client


def set_redis_client(client: redis.Redis) -> None:
    """Override the module-level Redis client — used by tests (e.g. fakeredis)."""
    global _redis_client
    _redis_client = client


def _rate_limit_key(scope: str) -> str:
    user_id = getattr(g, "user_id", None)
    identity = user_id if user_id else (request.remote_addr or "unknown")
    return f"ratelimit:{scope}:{identity}"


def rate_limit(limit: int, window_seconds: int, scope: str = "default"):
    """Decorator enforcing `limit` requests per `window_seconds` per client.

    Client identity is the authenticated user id (from `flask.g.user_id`, set
    by `require_auth`) when available, else the request's remote IP address.
    Returns HTTP 429 with a JSON error body when the limit is exceeded.
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            client = get_redis_client()
            key = _rate_limit_key(scope)
            try:
                current = client.incr(key)
                if current == 1:
                    client.expire(key, window_seconds)
            except redis.RedisError:
                # Fail open: if Redis is unreachable, don't block traffic.
                return view_func(*args, **kwargs)

            if current > limit:
                retry_after = client.ttl(key)
                response = jsonify(
                    {
                        "error": "Rate limit exceeded",
                        "limit": limit,
                        "window_seconds": window_seconds,
                        "retry_after_seconds": max(retry_after, 0),
                    }
                )
                response.status_code = 429
                if retry_after and retry_after > 0:
                    response.headers["Retry-After"] = str(retry_after)
                return response

            return view_func(*args, **kwargs)

        return wrapper

    return decorator
