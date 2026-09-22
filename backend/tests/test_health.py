"""Tests for the health endpoints."""

from __future__ import annotations

from unittest.mock import patch


def test_health_endpoint_requires_no_auth(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


def test_services_health_aggregates_downstream_status(client):
    class FakeResponse:
        ok = True
        status_code = 200

    with patch("routes.health.requests.get", return_value=FakeResponse()):
        resp = client.get("/services/health")

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["gateway"] == "ok"
    assert body["services"]["users-service"]["status"] == "ok"
    assert body["services"]["posts-service"]["status"] == "ok"


def test_services_health_reports_unreachable_service(client):
    import requests

    with patch("routes.health.requests.get", side_effect=requests.exceptions.ConnectionError("refused")):
        resp = client.get("/services/health")

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["services"]["users-service"]["status"] == "unreachable"
