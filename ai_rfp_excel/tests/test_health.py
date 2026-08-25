import pytest
from httpx import ASGITransport, AsyncClient

from ai_rfp_excel.app.main import app


@pytest.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health_endpoint_returns_200(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_response_structure(client: AsyncClient) -> None:
    response = await client.get("/health")
    data = response.json()
    assert "status" in data
    assert "services" in data
    assert isinstance(data["services"], list)


@pytest.mark.asyncio
async def test_health_checks_postgres(client: AsyncClient) -> None:
    response = await client.get("/health")
    data = response.json()
    services = data["services"]
    postgres_services = [s for s in services if s["name"] == "postgresql"]
    assert len(postgres_services) == 1
    assert "status" in postgres_services[0]


@pytest.mark.asyncio
async def test_health_checks_ollama(client: AsyncClient) -> None:
    response = await client.get("/health")
    data = response.json()
    services = data["services"]
    ollama_services = [s for s in services if s["name"] == "ollama"]
    assert len(ollama_services) == 1
    assert "status" in ollama_services[0]
