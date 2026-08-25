from contextlib import asynccontextmanager
from typing import AsyncGenerator

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic_settings import BaseSettings

from app.api.auth_routes import router as auth_router
from app.api.processing_routes import router as processing_router
from app.errors import AppError
from app.logging_config import setup_logging, get_logger


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://tender_user:tender_password@localhost:5432/tender_db"
    ollama_base_url: str = "http://localhost:11434"
    upload_dir: str = "./data/uploads"
    processed_dir: str = "./data/processed"
    extracted_dir: str = "./data/extracted"
    images_dir: str = "./data/images"
    ocr_dir: str = "./data/ocr"
    generated_dir: str = "./data/generated"
    secret_key: str = "change-in-production"
    default_model: str = "llama3.2:3b"
    log_level: str = "INFO"
    log_file: str | None = None

    class Config:
        env_file = ".env"


settings = Settings()
logger = get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    setup_logging(settings.log_level, settings.log_file)
    logger.info("starting_up")

    from app.database.connection import init_db, create_tables

    init_db(settings.database_url)
    await create_tables()
    logger.info("database_initialized")

    yield

    logger.info("shutting_down")


app = FastAPI(
    title="AI RFP Excel Generator",
    description="Local AI-based RFP PDF-to-Excel automation system",
    version="0.1.0",
    lifespan=lifespan,
)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.error_code,
                "message": exc.detail,
            }
        },
    )


app.include_router(auth_router)
app.include_router(processing_router)


@app.get("/health")
async def health_check():
    health = {"status": "healthy", "ollama": "unknown", "database": "unknown"}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{settings.ollama_base_url}/api/tags", timeout=5.0)
            health["ollama"] = "healthy" if response.status_code == 200 else "unhealthy"
    except Exception:
        health["ollama"] = "unhealthy"

    try:
        from sqlalchemy import text
        from app.database.connection import async_session_factory
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        health["database"] = "healthy"
    except Exception:
        health["database"] = "unhealthy"

    if health["ollama"] == "unhealthy" or health["database"] == "unhealthy":
        health["status"] = "degraded"

    return health


@app.get("/")
async def root():
    return {
        "name": "AI RFP Excel Generator",
        "version": "0.1.0",
        "docs": "/docs",
    }
