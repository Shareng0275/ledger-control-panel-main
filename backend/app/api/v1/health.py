from fastapi import APIRouter, status
from app.core.config import settings
from app.core.database import check_database_connection
from app.schemas.health import HealthResponse
from app.utils.timezone import utc_now

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Application Health Check",
    description="Returns the overall operational and database connectivity health status.",
)
async def health_check() -> HealthResponse:
    db_ok = await check_database_connection()
    return HealthResponse(
        status="healthy" if db_ok else "degraded",
        app_name=settings.APP_NAME,
        environment=settings.ENVIRONMENT,
        timestamp=utc_now(),
        database_connected=db_ok,
        details={
            "database": "connected" if db_ok else "unreachable",
        },
    )
