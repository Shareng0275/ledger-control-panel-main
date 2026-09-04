import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.pagination import PaginationParams, get_pagination_params
from app.db.session import get_db_session
from app.models import Membership, User
from app.schemas.audit import AuditListResponse
from app.services.audit_service import AuditService

router = APIRouter(prefix="/audit", tags=["Audit Trail"])


@router.get(
    "",
    response_model=AuditListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Organization Immutable Audit Trail",
    description=(
        "Retrieves chronological, append-only immutable audit records for the organization with "
        "filters for date ranges, actions, entity types, entity IDs, and reconciliation runs."
    ),
)
async def list_audit_trail(
    run_id: Optional[uuid.UUID] = Query(default=None, alias="run_id", description="Filter by reconciliation run ID"),
    action: Optional[str] = Query(default=None, description="Filter by action name (e.g. auth.login, reconciliation.completed)"),
    entity_type: Optional[str] = Query(default=None, description="Filter by entity type (e.g. User, Upload, ReconciliationRun, Exception)"),
    entity_id: Optional[uuid.UUID] = Query(default=None, description="Filter by entity primary key"),
    start_date: Optional[datetime] = Query(default=None, description="Filter records created after this UTC datetime"),
    end_date: Optional[datetime] = Query(default=None, description="Filter records created before this UTC datetime"),
    pagination: PaginationParams = Depends(get_pagination_params),
    x_organization_id: Optional[str] = Header(default=None, alias="X-Organization-Id"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> AuditListResponse:
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

    # 2. Query Audit Trail via AuditService
    return await AuditService.list_audit_trail(
        db=db,
        organization_id=target_org_id,
        pagination=pagination,
        start_date=start_date,
        end_date=end_date,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        run_id=run_id,
    )
