import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check_endpoint(async_client: AsyncClient):
    """Test root health check endpoint returns 200 and expected structure."""
    response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["app_name"] == "Ledger Control API"
    assert "timestamp" in data
    assert "database_connected" in data


@pytest.mark.asyncio
async def test_api_v1_health_check_endpoint(async_client: AsyncClient):
    """Test /api/v1/health endpoint."""
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["app_name"] == "Ledger Control API"
