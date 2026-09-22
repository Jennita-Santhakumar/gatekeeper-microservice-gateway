"""Tests for the proxy routes: auth enforcement and successful proxying with
the downstream call mocked out (core.circuit.proxy_request)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from core.security import create_access_token


def test_proxy_users_requires_auth(client):
    resp = client.get("/api/users/1")
    assert resp.status_code == 401


def test_proxy_posts_requires_auth(client):
    resp = client.get("/api/posts/1")
    assert resp.status_code == 401


def test_proxy_users_forwards_and_returns_downstream_response(client, app):
    token = None
    with app.app_context():
        token = create_access_token(user_id=1, email="a@example.com")

    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = {"id": 1, "email": "a@example.com"}

    with patch("routes.proxy.proxy_request", return_value=fake_response) as mock_proxy:
        resp = client.get("/api/users/1", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 200
    assert resp.get_json() == {"id": 1, "email": "a@example.com"}
    mock_proxy.assert_called_once()
    _, kwargs = mock_proxy.call_args
    assert kwargs["service"] == "users"


def test_proxy_returns_503_when_circuit_open(client, app):
    from circuitbreaker import CircuitBreakerError

    with app.app_context():
        token = create_access_token(user_id=1, email="a@example.com")

    with patch("routes.proxy.proxy_request", side_effect=CircuitBreakerError(MagicMock())):
        resp = client.get("/api/posts/1", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 503


def test_proxy_rejects_malformed_auth_header(client):
    resp = client.get("/api/users/1", headers={"Authorization": "NotBearer abc"})
    assert resp.status_code == 401
