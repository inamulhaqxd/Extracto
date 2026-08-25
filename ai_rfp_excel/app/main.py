from fastapi import FastAPI

from ai_rfp_excel.app.config import settings

app = FastAPI(
    title=settings.APP_NAME,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)


@app.get("/ping")
async def ping():
    return {"message": "pong"}
