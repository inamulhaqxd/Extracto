from dataclasses import dataclass
from typing import Any

import httpx
from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ai_rfp_excel.app.api.deps import get_db
from ai_rfp_excel.app.config import settings

router = APIRouter(tags=["health"])


@dataclass
class ServiceStatus:
    name: str
    status: str
    message: str


@dataclass
class HealthResponse:
    status: str
    services: list[ServiceStatus]


async def check_postgres(db: AsyncSession) -> ServiceStatus:
    try:
        await db.execute(text("SELECT 1"))
        return ServiceStatus(name="postgresql", status="healthy", message="Connection successful")
    except Exception as e:
        return ServiceStatus(name="postgresql", status="unhealthy", message=str(e))


async def check_ollama() -> ServiceStatus:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            if response.status_code == 200:
                return ServiceStatus(name="ollama", status="healthy", message="Connection successful")
            return ServiceStatus(name="ollama", status="unhealthy", message=f"HTTP {response.status_code}")
    except Exception as e:
        return ServiceStatus(name="ollama", status="unhealthy", message=str(e))


@router.get("/health")
async def health_check() -> dict[str, Any]:
    db: AsyncSession
    async for db in get_db():
        postgres_status = await check_postgres(db)
        break

    ollama_status = await check_ollama()

    services = [postgres_status, ollama_status]

    all_healthy = all(s.status == "healthy" for s in services)
    overall_status = "healthy" if all_healthy else "degraded"

    return {
        "status": overall_status,
        "services": [
            {"name": s.name, "status": s.status, "message": s.message}
            for s in services
        ],
    }
