from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import api_v1_router
from app.api.v1.health import router as health_root_router
from app.core.config import settings
from app.core.database import check_database_connection, close_database_connection
from app.core.exceptions import register_exception_handlers
from app.core.logging import logger, setup_logging

OPENAPI_TAGS = [
    {"name": "Authentication", "description": "User registration, login, token rotation, and sessions"},
    {"name": "Health", "description": "Service availability and database connectivity health checks"},
    {"name": "Transactions", "description": "Paginated transaction search, multi-tenant filtering, and sorting"},
    {"name": "Uploads", "description": "Bank statement and internal/gateway ledger CSV ingestion"},
    {"name": "Reconciliation", "description": "Automated matching engine runs and progress tracking"},
    {"name": "Exceptions", "description": "Discrepancy review, confidence thresholds, and resolutions"},
    {"name": "Cash Forecasting", "description": "Multi-horizon cash flow projections"},
    {"name": "Financial AI Intelligence", "description": "Conversational assistant for ledger analysis"},
    {"name": "Audit Trail", "description": "Chronological immutable compliance log per organization"},
    {"name": "Insights", "description": "Summary and anomaly intelligence reports"},
]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown lifecycle management."""
    setup_logging()
    logger.info(f"Starting {settings.APP_NAME} in [{settings.ENVIRONMENT}] environment")

    # Verify initial database connectivity on startup
    db_connected = await check_database_connection()
    if db_connected:
        logger.info("Database connectivity established successfully.")
    else:
        logger.warning("Database connection is currently unreachable; running in degraded mode.")

    yield

    # Clean up database resources on shutdown
    logger.info(f"Shutting down {settings.APP_NAME}...")
    await close_database_connection()
    logger.info("Shutdown complete.")


def create_application() -> FastAPI:
    """FastAPI application factory."""
    app = FastAPI(
        title=settings.APP_NAME,
        description="AI-powered financial reconciliation and financial intelligence platform backend API.",
        version="0.1.0",
        openapi_tags=OPENAPI_TAGS,
        lifespan=lifespan,
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
    )

    # Register Global Exception Handlers (400, 401, 403, 404, 409, 422, 429, 500)
    register_exception_handlers(app)

    # Security Headers Middleware
    from app.core.security_headers import SecurityHeadersMiddleware
    app.add_middleware(SecurityHeadersMiddleware)

    # CORS Middleware configured for frontend integration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Root Health check route (/health)
    app.include_router(health_root_router)

    # Versioned API Routes (/api/v1/... and /v1/...)
    from app.api.v1 import v1_router
    app.include_router(api_v1_router)
    app.include_router(v1_router)

    return app


app = create_application()
