from __future__ import annotations

from fastapi.testclient import TestClient


def _create_user(client: TestClient, email: str = "jane@example.com") -> dict:
    response = client.post(
        "/users",
        json={"email": email, "username": "jane", "password": "supersecret123"},
    )
    return response


def test_health_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"


def test_create_user_returns_201_and_no_password(client: TestClient) -> None:
    response = _create_user(client)
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "jane@example.com"
    assert body["username"] == "jane"
    assert "id" in body
    assert "created_at" in body
    assert "password" not in body
    assert "hashed_password" not in body


def test_create_user_duplicate_email_returns_409(client: TestClient) -> None:
    first = _create_user(client)
    assert first.status_code == 201

    second = _create_user(client)
    assert second.status_code == 409


def test_get_user_by_id(client: TestClient) -> None:
    created = _create_user(client).json()
    response = client.get(f"/users/{created['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_missing_user_returns_404(client: TestClient) -> None:
    response = client.get("/users/does-not-exist")
    assert response.status_code == 404


def test_list_users_paginated(client: TestClient) -> None:
    for i in range(3):
        _create_user(client, email=f"user{i}@example.com")

    response = client.get("/users", params={"limit": 2, "offset": 0})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2
    assert body["limit"] == 2
    assert body["offset"] == 0

    response2 = client.get("/users", params={"limit": 2, "offset": 2})
    assert len(response2.json()["items"]) == 1
