from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from ai_rfp_excel.app.api.errors import (
    ConfigurationError,
    DocumentError,
    ProcessingError,
    ValidationError,
)
from ai_rfp_excel.app.main import app


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_app_error_returns_json(client: AsyncClient) -> None:
    response = await client.get("/nonexistent")
    assert response.status_code == 404
    data = response.json()
    assert data["error"] is True
    assert "message" in data


def test_document_error_message() -> None:
    err = DocumentError("file not found")
    assert err.message == "Document issue: file not found"
    assert err.status_code == 422


def test_processing_error_message() -> None:
    err = ProcessingError("extraction failed")
    assert err.message == "Processing failed: extraction failed"
    assert err.status_code == 500


def test_validation_error_message() -> None:
    err = ValidationError("invalid input")
    assert err.message == "Validation failed: invalid input"
    assert err.status_code == 422


def test_configuration_error_message() -> None:
    err = ConfigurationError("missing key")
    assert err.message == "Configuration error: missing key"
    assert err.status_code == 500
