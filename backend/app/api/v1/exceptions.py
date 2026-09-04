import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from app.api.deps import get_current_user, require_roles
from app.core.pagination import PaginationParams, get_pagination_params, paginate_select
from app.db.session import get_db_session
from app.models import (
    ExceptionPriority,
    ExceptionStatus,
    Membership,
    MembershipRole,
    ReconciliationException,
    Transaction,
    User,
)
from app.schemas.exception import (
    BulkResolveRequest,
    BulkResolveResponse,
    ExceptionListResponse,
    ExceptionResponse,
    ExceptionReviewDetailResponse,
    ResolveExceptionRequest,
    ResolveExceptionResponse,
    TransactionSummaryDTO,
)
from app.services.exception_service import ExceptionService

router = APIRouter(prefix="/exceptions", tags=["Exceptions"])


@router.get(
    "",
    response_model=ExceptionListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Reconciliation Exceptions",
)
async def list_exceptions(
    run_id: Optional[uuid.UUID] = Query(default=None, alias="run_id"),
    status_filter: Optional[ExceptionStatus] = Query(default=None, alias="status"),
    priority_filter: Optional[ExceptionPriority] = Query(default=None, alias="priority"),
    search: Optional[str] = Query(default=None, alias="search"),
    sort_by: str = Query(default="created_at", alias="sort_by"),
    sort_order: str = Query(default="desc", alias="sort_order"),
    pagination: PaginationParams = Depends(get_pagination_params),
    x_organization_id: Optional[str] = Header(default=None, alias="X-Organization-Id"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ExceptionListResponse:
    """List exceptions for an organization with status/priority filtering and pagination."""
    target_org_id: Optional[uuid.UUID] = None
    if x_organization_id:
        target_org_id = uuid.UUID(x_organization_id)
        # Verify user membership in header org
        m_stmt = select(Membership).where(
            Membership.user_id == current_user.id,
            Membership.organization_id == target_org_id,
        )
        m_res = await db.execute(m_stmt)
        if not m_res.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User does not have access to this organization.",
            )
    else:
        m_stmt = select(Membership.organization_id).where(Membership.user_id == current_user.id).limit(1)
        res = await db.execute(m_stmt)
        target_org_id = res.scalar_one_or_none()

    if not target_org_id:
        return ExceptionListResponse(
            items=[],
            exceptions=[],
            total=0,
            page=pagination.page,
            page_size=pagination.page_size,
            total_pages=1,
            has_next=False,
            has_prev=False,
        )

    query = (
        select(ReconciliationException)
        .where(ReconciliationException.organization_id == target_org_id)
        .options(
            joinedload(ReconciliationException.transaction),
            joinedload(ReconciliationException.best_candidate_transaction),
        )
    )

    if run_id:
        query = query.where(ReconciliationException.reconciliation_run_id == run_id)
    if status_filter:
        query = query.where(ReconciliationException.status == status_filter)
    if priority_filter:
        query = query.where(ReconciliationException.priority == priority_filter)
    if search:
        query = query.where(ReconciliationException.reason_text.ilike(f"%{search}%"))

    # Resolve sort column safely
    sort_column_map = {
        "created_at": ReconciliationException.created_at,
        "priority": ReconciliationException.priority,
        "status": ReconciliationException.status,
    }
    sort_col = sort_column_map.get(sort_by, ReconciliationException.created_at)

    items, total, total_pages = await paginate_select(
        db=db,
        select_query=query,
        page_params=pagination,
        sort_column=sort_col,
        sort_order=sort_order,
    )

    dtos = []
    for item in items:
        tx = item.transaction
        cand = item.best_candidate_transaction
        dto = ExceptionResponse(
            id=item.id,
            reconciliation_run_id=item.reconciliation_run_id,
            transaction_id=item.transaction_id,
            best_candidate_transaction_id=item.best_candidate_transaction_id,
            reason_text=item.reason_text,
            priority=item.priority,
            status=item.status,
            resolution_action=item.resolution_action,
            resolved_by=item.resolved_by,
            resolved_at=item.resolved_at,
            created_at=item.created_at,
            amount=tx.amount if tx else None,
            date=tx.transaction_date if tx else None,
            currency=tx.currency if tx else None,
            confidence=tx.confidence if tx else None,
            transaction=TransactionSummaryDTO.model_validate(tx) if tx else None,
            best_candidate_transaction=TransactionSummaryDTO.model_validate(cand) if cand else None,
        )
        dtos.append(dto)

    return ExceptionListResponse(
        items=dtos,
        exceptions=dtos,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=total_pages,
        has_next=pagination.page < total_pages,
        has_prev=pagination.page > 1,
    )


@router.get(
    "/{exception_id}",
    response_model=ExceptionReviewDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Single Exception for Review Drawer",
)
async def get_exception_detail(
    exception_id: uuid.UUID,
    x_organization_id: Optional[str] = Header(default=None, alias="X-Organization-Id"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ExceptionReviewDetailResponse:
    """Retrieve full transaction pairs and explanation breakdown for the frontend review drawer."""
    # Determine and authorize organization
    target_org_id = uuid.UUID(x_organization_id) if x_organization_id else None
    if not target_org_id:
        m_stmt = select(Membership.organization_id).where(Membership.user_id == current_user.id).limit(1)
        res = await db.execute(m_stmt)
        target_org_id = res.scalar_one_or_none()

    if not target_org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No active organization found.")

    # Verify user membership in target org
    m_check = select(Membership).where(
        Membership.user_id == current_user.id,
        Membership.organization_id == target_org_id,
    )
    m_res = await db.execute(m_check)
    if not m_res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not have access to this organization.",
        )

    exc = await ExceptionService.get_exception(db, exception_id, target_org_id)

    stmt_dto = TransactionSummaryDTO.model_validate(exc.transaction)
    cand_dto = TransactionSummaryDTO.model_validate(exc.best_candidate_transaction) if exc.best_candidate_transaction else None

    # Parse or assemble explanation details
    explanation_details = {
        "reason": exc.reason_text,
        "priority": exc.priority.value,
        "confidence": str(exc.transaction.confidence) if exc.transaction and exc.transaction.confidence else None,
    }

    return ExceptionReviewDetailResponse(
        id=exc.id,
        reconciliation_run_id=exc.reconciliation_run_id,
        priority=exc.priority,
        status=exc.status,
        reason=exc.reason_text,
        created_at=exc.created_at,
        resolved_at=exc.resolved_at,
        resolution_action=exc.resolution_action,
        statement_transaction=stmt_dto,
        candidate_transaction=cand_dto,
        explanation_details=explanation_details,
    )


@router.post(
    "/{exception_id}/resolve",
    response_model=ResolveExceptionResponse,
    status_code=status.HTTP_200_OK,
    summary="Resolve Single Exception (Confirm Match or Reject)",
    dependencies=[Depends(require_roles(MembershipRole.ANALYST, MembershipRole.ADMIN))],
)
async def resolve_exception(
    exception_id: uuid.UUID,
    payload: ResolveExceptionRequest,
    x_organization_id: Optional[str] = Header(default=None, alias="X-Organization-Id"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ResolveExceptionResponse:
    """Manually resolve an exception by confirming a match or rejecting."""
    target_org_id = uuid.UUID(x_organization_id) if x_organization_id else None
    if not target_org_id:
        m_stmt = select(Membership.organization_id).where(Membership.user_id == current_user.id).limit(1)
        res = await db.execute(m_stmt)
        target_org_id = res.scalar_one_or_none()

    if not target_org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No active organization.")

    return await ExceptionService.resolve_single_exception(
        db=db,
        exception_id=exception_id,
        organization_id=target_org_id,
        user_id=current_user.id,
        action=payload.action,
        candidate_id=payload.candidate_id,
        note=payload.note,
    )


@router.post(
    "/bulk-resolve",
    response_model=BulkResolveResponse,
    status_code=status.HTTP_200_OK,
    summary="Bulk Resolve Exceptions",
    dependencies=[Depends(require_roles(MembershipRole.ANALYST, MembershipRole.ADMIN))],
)
async def bulk_resolve_exceptions(
    payload: BulkResolveRequest,
    x_organization_id: Optional[str] = Header(default=None, alias="X-Organization-Id"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> BulkResolveResponse:
    """Resolve multiple exceptions in batch with transactional integrity."""
    target_org_id = uuid.UUID(x_organization_id) if x_organization_id else None
    if not target_org_id:
        m_stmt = select(Membership.organization_id).where(Membership.user_id == current_user.id).limit(1)
        res = await db.execute(m_stmt)
        target_org_id = res.scalar_one_or_none()

    if not target_org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No active organization.")

    return await ExceptionService.resolve_bulk_exceptions(
        db=db,
        exception_ids=payload.exception_ids,
        organization_id=target_org_id,
        user_id=current_user.id,
        action=payload.action,
        note=payload.note,
    )
