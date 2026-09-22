"""Tests for the Redis-backed rate limiter, using fakeredis in place of real Redis."""

from __future__ import annotations

import fakeredis
from flask import Flask

from core.rate_limit import rate_limit, set_redis_client


def _build_app():
    app = Flask(__name__)

    @app.get("/limited")
    @rate_limit(limit=3, window_seconds=60, scope="test")
    def limited():
        return {"ok": True}, 200

    return app


def test_requests_under_limit_pass_through():
    set_redis_client(fakeredis.FakeStrictRedis(decode_responses=True))
    app = _build_app()
    client = app.test_client()

    for _ in range(3):
        resp = client.get("/limited")
        assert resp.status_code == 200


def test_requests_over_limit_return_429_with_json_body():
    set_redis_client(fakeredis.FakeStrictRedis(decode_responses=True))
    app = _build_app()
    client = app.test_client()

    for _ in range(3):
        client.get("/limited")

    resp = client.get("/limited")
    assert resp.status_code == 429
    body = resp.get_json()
    assert body["error"] == "Rate limit exceeded"
    assert body["limit"] == 3


def test_rate_limit_fails_open_when_redis_unavailable():
    class BrokenRedis:
        def incr(self, *_args, **_kwargs):
            raise ConnectionError("redis down")

    import redis as redis_module

    class FakeBroken(BrokenRedis):
        def incr(self, *_args, **_kwargs):
            raise redis_module.RedisError("down")

    set_redis_client(FakeBroken())
    app = _build_app()
    client = app.test_client()

    resp = client.get("/limited")
    assert resp.status_code == 200
