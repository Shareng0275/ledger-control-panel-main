from typing import Any, Optional
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.core.logging import logger


class AppException(Exception):
    """Base application exception."""
    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        code: Optional[str] = None,
        details: Optional[Any] = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code
        self.details = details


class NotFoundError(AppException):
    def __init__(self, message: str = "Resource not found.", code: str = "NOT_FOUND"):
        super().__init__(message=message, status_code=status.HTTP_404_NOT_FOUND, code=code)


class ConflictError(AppException):
    def __init__(self, message: str = "Resource conflict.", code: str = "CONFLICT"):
        super().__init__(message=message, status_code=status.HTTP_409_CONFLICT, code=code)


class PermissionDeniedError(AppException):
    def __init__(self, message: str = "Permission denied.", code: str = "FORBIDDEN"):
        super().__init__(message=message, status_code=status.HTTP_403_FORBIDDEN, code=code)


class RateLimitError(AppException):
    def __init__(self, message: str = "Too many requests.", code: str = "RATE_LIMIT_EXCEEDED"):
        super().__init__(message=message, status_code=status.HTTP_429_TOO_MANY_REQUESTS, code=code)


def _format_http_error(status_code: int, detail: Any) -> tuple[str, str]:
    error_name = "HttpException"
    if status_code == status.HTTP_400_BAD_REQUEST:
        error_name = "BadRequest"
    elif status_code == status.HTTP_401_UNAUTHORIZED:
        error_name = "Unauthorized"
    elif status_code == status.HTTP_403_FORBIDDEN:
        error_name = "Forbidden"
    elif status_code == status.HTTP_404_NOT_FOUND:
        error_name = "NotFound"
    elif status_code == status.HTTP_409_CONFLICT:
        error_name = "Conflict"
    elif status_code == status.HTTP_429_TOO_MANY_REQUESTS:
        error_name = "TooManyRequests"
    return error_name, str(detail)


def register_exception_handlers(app: FastAPI) -> None:
    """Register uniform global exception handlers on the FastAPI application."""

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.__class__.__name__,
                "detail": exc.message,
                "status_code": exc.status_code,
                "code": exc.code,
                "details": exc.details,
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def starlette_http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        error_name, detail = _format_http_error(exc.status_code, exc.detail)
        headers = getattr(exc, "headers", None)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": error_name,
                "detail": detail,
                "status_code": exc.status_code,
            },
            headers=headers,
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        error_name, detail = _format_http_error(exc.status_code, exc.detail)
        headers = getattr(exc, "headers", None)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": error_name,
                "detail": detail,
                "status_code": exc.status_code,
            },
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = exc.errors()
        logger.warning(f"Validation error on {request.method} {request.url.path}: {errors}")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "ValidationError",
                "detail": "Request payload validation failed.",
                "status_code": status.HTTP_422_UNPROCESSABLE_ENTITY,
                "errors": errors,
            },
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        # Log complete stack trace internally without exposing it to clients
        logger.exception(f"Unhandled exception processing {request.method} {request.url.path}: {exc}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "InternalServerError",
                "detail": "An unexpected error occurred. Please contact support if the issue persists.",
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            },
        )
