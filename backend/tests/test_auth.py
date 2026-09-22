"""Tests for auth register/login routes using the Flask test client and an
in-memory SQLite DB (see conftest.py). Calls to users-service are mocked."""

from __future__ import annotations

from unittest.mock import patch


def test_register_creates_user_and_returns_token(client):
    with patch("routes.auth.requests.post") as mock_post:
        mock_post.return_value.ok = True
        resp = client.post("/auth/register", json={"email": "new@example.com", "password": "hunter2pass"})

    assert resp.status_code == 201
    body = resp.get_json()
    assert body["email"] == "new@example.com"
    assert "access_token" in body
    mock_post.assert_called_once()


def test_register_succeeds_even_if_users_service_unreachable(client):
    import requests

    with patch("routes.auth.requests.post", side_effect=requests.exceptions.ConnectionError("refused")):
        resp = client.post("/auth/register", json={"email": "resilient@example.com", "password": "hunter2pass"})

    assert resp.status_code == 201
    assert "access_token" in resp.get_json()


def test_register_rejects_duplicate_email(client):
    with patch("routes.auth.requests.post") as mock_post:
        mock_post.return_value.ok = True
        client.post("/auth/register", json={"email": "dup@example.com", "password": "hunter2pass"})
        resp = client.post("/auth/register", json={"email": "dup@example.com", "password": "hunter2pass"})

    assert resp.status_code == 409


def test_register_rejects_short_password(client):
    resp = client.post("/auth/register", json={"email": "short@example.com", "password": "123"})
    assert resp.status_code == 400


def test_login_with_correct_credentials_returns_token(client):
    with patch("routes.auth.requests.post") as mock_post:
        mock_post.return_value.ok = True
        client.post("/auth/register", json={"email": "login@example.com", "password": "hunter2pass"})

    resp = client.post("/auth/login", json={"email": "login@example.com", "password": "hunter2pass"})
    assert resp.status_code == 200
    assert "access_token" in resp.get_json()


def test_login_with_wrong_password_returns_401(client):
    with patch("routes.auth.requests.post") as mock_post:
        mock_post.return_value.ok = True
        client.post("/auth/register", json={"email": "wrongpw@example.com", "password": "hunter2pass"})

    resp = client.post("/auth/login", json={"email": "wrongpw@example.com", "password": "nope-nope"})
    assert resp.status_code == 401


def test_login_with_unknown_email_returns_401(client):
    resp = client.post("/auth/login", json={"email": "ghost@example.com", "password": "hunter2pass"})
    assert resp.status_code == 401
