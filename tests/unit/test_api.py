"""Tests for Audio Processor FastAPI Application."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from audio_processor.api import APP_DESCRIPTION, APP_TITLE, APP_VERSION, app


@pytest.fixture
def client() -> TestClient:
    """Create a test client for the FastAPI app."""
    return TestClient(app)


class TestHealthEndpoint:
    """Tests for the /health endpoint."""

    def test_health_check_returns_healthy(self, client: TestClient) -> None:
        """Health check should return healthy status."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}

    def test_health_check_content_type(self, client: TestClient) -> None:
        """Health check should return JSON content type."""
        response = client.get("/health")
        assert response.headers["content-type"] == "application/json"


class TestRootEndpoint:
    """Tests for the root endpoint."""

    def test_root_returns_api_info(self, client: TestClient) -> None:
        """Root endpoint should return API information."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == APP_TITLE
        assert data["version"] == APP_VERSION
        assert data["docs"] == "/docs"

    def test_root_content_type(self, client: TestClient) -> None:
        """Root endpoint should return JSON content type."""
        response = client.get("/")
        assert response.headers["content-type"] == "application/json"


class TestAPIMetadata:
    """Tests for API metadata."""

    def test_app_title(self) -> None:
        """App should have correct title."""
        assert app.title == APP_TITLE

    def test_app_version(self) -> None:
        """App should have correct version."""
        assert app.version == APP_VERSION

    def test_app_description(self) -> None:
        """App should have correct description."""
        assert app.description == APP_DESCRIPTION


class TestDocsEndpoints:
    """Tests for documentation endpoints."""

    def test_swagger_ui_available(self, client: TestClient) -> None:
        """Swagger UI should be available at /docs."""
        response = client.get("/docs")
        assert response.status_code == 200
        assert "swagger" in response.text.lower() or "html" in response.text.lower()

    def test_redoc_available(self, client: TestClient) -> None:
        """ReDoc should be available at /redoc."""
        response = client.get("/redoc")
        assert response.status_code == 200
        assert "redoc" in response.text.lower() or "html" in response.text.lower()

    def test_openapi_json_available(self, client: TestClient) -> None:
        """OpenAPI JSON should be available."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "info" in data
        assert data["info"]["title"] == APP_TITLE
