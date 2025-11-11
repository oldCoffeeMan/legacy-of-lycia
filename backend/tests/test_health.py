"""
Tests for health check endpoint.
"""
import pytest
from fastapi.testclient import TestClient


def test_health_endpoint_returns_ok(client: TestClient):
    """
    Test that /health endpoint returns status ok.

    Args:
        client: FastAPI test client fixture
    """
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_endpoint_no_authentication_required(client: TestClient):
    """
    Test that /health endpoint doesn't require authentication.

    Args:
        client: FastAPI test client fixture
    """
    # No session/auth headers provided
    response = client.get("/health")

    assert response.status_code == 200
    # Endpoint should be accessible without auth
