import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db_session
from app.models import Membership, User
from app.schemas.forecast import ForecastResponse
from app.services.forecasting_service import ForecastingService

router = APIRouter(prefix="/forecast", tags=["Cash Forecasting"])


@router.get(
    "",
    response_model=ForecastResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Statistical Cash Flow Forecast",
    description=(
        "Calculates an explainable statistical cash forecast (7d, 30d, 90d) from actual historical "
        "financial transaction data with expanding uncertainty confidence bands."
    ),
)
async def get_forecast(
    horizon: str = Query(
        default="30d",
        pattern="^(7d|30d|90d)$",
        description="Forecast horizon ('7d', '30d', or '90d')",
    ),
    x_organization_id: Optional[str] = Header(default=None, alias="X-Organization-Id"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ForecastResponse:
    # 1. Resolve Multi-Tenant Organization Context
    target_org_id: Optional[uuid.UUID] = None
    if x_organization_id:
        try:
            target_org_id = uuid.UUID(x_organization_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid 'X-Organization-Id' header format. Must be a valid UUID.",
            )
        # Verify user belongs to requested organization
        m_stmt = select(Membership).where(
            Membership.organization_id == target_org_id,
            Membership.user_id == current_user.id,
        )
        m_res = await db.execute(m_stmt)
        if not m_res.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You do not have membership in this organization.",
            )
    else:
        # Fallback to user's first active organization membership
        m_stmt = (
            select(Membership.organization_id)
            .where(Membership.user_id == current_user.id)
            .limit(1)
        )
        m_res = await db.execute(m_stmt)
        target_org_id = m_res.scalar_one_or_none()

    if not target_org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active organization context found for this user.",
        )

    # 2. Execute Statistical Forecasting Engine
    return await ForecastingService.generate_forecast(
        db=db,
        organization_id=target_org_id,
        horizon_str=horizon,
    )
