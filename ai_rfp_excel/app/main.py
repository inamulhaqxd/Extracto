from fastapi import FastAPI
from fastapi.responses import JSONResponse

from ai_rfp_excel.app.api.auth import router as auth_router
from ai_rfp_excel.app.config import settings

app = FastAPI(
    title=settings.APP_NAME,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

app.include_router(auth_router)


@app.get("/ping")
async def ping() -> JSONResponse:
    return JSONResponse(content={"message": "pong"})
