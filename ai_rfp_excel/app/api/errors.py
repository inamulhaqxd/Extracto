from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    def __init__(self, message: str, status_code: int = 500) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class DocumentError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(message=f"Document issue: {message}", status_code=422)


class ProcessingError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(message=f"Processing failed: {message}", status_code=500)


class ValidationError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(message=f"Validation failed: {message}", status_code=422)


class ConfigurationError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(message=f"Configuration error: {message}", status_code=500)



def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": True,
                "message": exc.message,
                "type": type(exc).__name__,
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": True,
                "message": str(exc.detail),
                "type": "HTTPException",
            },
        )


    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": True,
                "message": "An unexpected error occurred. Please try again later.",
                "type": "InternalServerError",
            },
        )
