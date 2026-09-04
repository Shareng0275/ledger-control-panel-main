from fastapi import APIRouter
from app.api.v1.ask import router as ask_router
from app.api.v1.audit import router as audit_router
from app.api.v1.auth import router as auth_router
from app.api.v1.exceptions import router as exceptions_router
from app.api.v1.forecast import router as forecast_router
from app.api.v1.health import router as health_router
from app.api.v1.insights import router as insights_router
from app.api.v1.reconciliation import router as reconciliation_router
from app.api.v1.transactions import router as transactions_router
from app.api.v1.uploads import router as uploads_router

# Standard versioned API router (/api/v1)
api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(auth_router)
api_v1_router.include_router(health_router)
api_v1_router.include_router(transactions_router)
api_v1_router.include_router(uploads_router)
api_v1_router.include_router(reconciliation_router)
api_v1_router.include_router(exceptions_router)
api_v1_router.include_router(forecast_router)
api_v1_router.include_router(ask_router)
api_v1_router.include_router(audit_router)
api_v1_router.include_router(insights_router)

# Alias router (/v1) for flexible frontend compatibility
v1_router = APIRouter(prefix="/v1")
v1_router.include_router(auth_router)
v1_router.include_router(health_router)
v1_router.include_router(transactions_router)
v1_router.include_router(uploads_router)
v1_router.include_router(reconciliation_router)
v1_router.include_router(exceptions_router)
v1_router.include_router(forecast_router)
v1_router.include_router(ask_router)
v1_router.include_router(audit_router)
v1_router.include_router(insights_router)

__all__ = ["api_v1_router", "v1_router"]
