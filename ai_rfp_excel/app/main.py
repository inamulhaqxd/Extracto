from fastapi import FastAPI
from fastapi.responses import JSONResponse

from ai_rfp_excel.app.api.ai import router as ai_router
from ai_rfp_excel.app.api.auth import router as auth_router
from ai_rfp_excel.app.api.compliance import router as compliance_router
from ai_rfp_excel.app.api.errors import register_error_handlers
from ai_rfp_excel.app.api.excel import router as excel_router
from ai_rfp_excel.app.api.health import router as health_router
from ai_rfp_excel.app.api.pdf import router as pdf_router
from ai_rfp_excel.app.config import settings
from ai_rfp_excel.app.logging import setup_logging

setup_logging()

app = FastAPI(
    title=settings.APP_NAME,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

register_error_handlers(app)

app.include_router(auth_router)
app.include_router(health_router)
app.include_router(pdf_router)
app.include_router(excel_router)
app.include_router(ai_router)
app.include_router(compliance_router)





@app.get("/ping")
async def ping() -> JSONResponse:
    return JSONResponse(content={"message": "pong"})
