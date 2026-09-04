import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db_session
from app.models import Membership, User
from app.schemas.insight import InsightsListResponse
from app.services.insights_service import InsightsService

router = APIRouter(prefix="/insights", tags=["AI Predictive Insights & Anomaly Detection"])


@router.get(
    "",
    response_model=InsightsListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Financial Insights & Predictive Anomalies",
    description=(
        "Retrieves explainable, evidence-based financial insights and detected anomalies across "
        "unusual amounts, burst frequencies, near duplicates, suspicious mismatches, and high-risk exceptions."
    ),
)
async def get_insights(
    run_id: Optional[uuid.UUID] = Query(default=None, alias="run_id", description="Filter by reconciliation run ID"),
    severity: Optional[str] = Query(
        default=None,
        pattern="^(critical|high|medium|low)$",
        description="Filter by severity level ('critical', 'high', 'medium', 'low')",
    ),
    category: Optional[str] = Query(
        default=None,
        pattern="^(unusual_amount|unusual_frequency|near_duplicate|suspicious_mismatch|high_risk_exception)$",
        description="Filter by anomaly category",
    ),
    x_organization_id: Optional[str] = Header(default=None, alias="X-Organization-Id"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> InsightsListResponse:
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

    # 2. Execute Predictive Insights Engine
    return await InsightsService.get_insights(
        db=db,
        organization_id=target_org_id,
        run_id=run_id,
        severity_filter=severity,
        category_filter=category,
    )
