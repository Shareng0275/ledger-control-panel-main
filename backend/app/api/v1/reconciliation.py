import uuid
from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, status
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.db.session import get_db_session
from app.models import Match, Membership, ReconciliationRun, Transaction, TransactionStatus, User
from app.schemas.reconciliation import (
    ConfidenceDistributionItem,
    ReconcileRunResponse,
    ReconciliationSummaryResponse,
    StartReconcileRequest,
)
from app.services.reconciliation_service import ReconciliationService

router = APIRouter(prefix="/reconcile", tags=["Reconciliation"])


# ─── Helper: Resolve + verify organization membership ───────────────────────
async def _resolve_org_id(
    current_user: User,
    db: AsyncSession,
    x_organization_id: Optional[str] = None,
) -> uuid.UUID:
    """Resolve and verify the target organization for the current user."""
    target_org_id: Optional[uuid.UUID] = None
    if x_organization_id:
        try:
            target_org_id = uuid.UUID(x_organization_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid 'X-Organization-Id' header format. Must be a valid UUID.",
            )
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
        m_stmt = select(Membership.organization_id).where(Membership.user_id == current_user.id).limit(1)
        res = await db.execute(m_stmt)
        target_org_id = res.scalar_one_or_none()

    if not target_org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active organization context found for this user.",
        )
    return target_org_id


# ─── POST /run ───────────────────────────────────────────────────────────────
@router.post(
    "/run",
    response_model=ReconcileRunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Trigger Asynchronous Deterministic Reconciliation",
    description="Initiates an asynchronous deterministic reconciliation matching run between bank statements and general ledger entries.",
)
async def trigger_reconciliation(
    payload: StartReconcileRequest,
    background_tasks: BackgroundTasks,
    x_organization_id: Optional[str] = Header(default=None, alias="X-Organization-Id"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ReconcileRunResponse:
    target_org_id = await _resolve_org_id(current_user, db, x_organization_id)

    # Validate Uploads
    stmt_upload, ledg_upload = await ReconciliationService.validate_uploads(
        db=db,
        organization_id=target_org_id,
        statement_upload_id=payload.statement_upload_id,
        ledger_upload_id=payload.ledger_upload_id,
    )

    # Create Run Record with status PROCESSING
    run = await ReconciliationService.create_run(
        db=db,
        organization_id=target_org_id,
        user_id=current_user.id,
        statement_upload_id=stmt_upload.id,
        ledger_upload_id=ledg_upload.id,
    )

    # Dispatch Asynchronous Background Job
    background_tasks.add_task(
        ReconciliationService.run_reconciliation_job,
        run_id=run.id,
        organization_id=target_org_id,
        user_id=current_user.id,
    )

    return ReconcileRunResponse.model_validate(run)


# ─── GET /{run_id} ───────────────────────────────────────────────────────────
@router.get(
    "/{run_id}",
    response_model=ReconcileRunResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Reconciliation Run Status & Metrics",
)
async def get_reconciliation_run_by_id(
    run_id: uuid.UUID,
    x_organization_id: Optional[str] = Header(default=None, alias="X-Organization-Id"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ReconcileRunResponse:
    return await _fetch_run(run_id, current_user, db, x_organization_id)


# ─── GET /runs/{run_id} (Alias) ─────────────────────────────────────────────
@router.get(
    "/runs/{run_id}",
    response_model=ReconcileRunResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Reconciliation Run Status & Metrics (Alias)",
)
async def get_reconciliation_run_alias(
    run_id: uuid.UUID,
    x_organization_id: Optional[str] = Header(default=None, alias="X-Organization-Id"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ReconcileRunResponse:
    return await _fetch_run(run_id, current_user, db, x_organization_id)


# ─── GET /{run_id}/summary ──────────────────────────────────────────────────
@router.get(
    "/{run_id}/summary",
    response_model=ReconciliationSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Dashboard KPI Summary for a Reconciliation Run",
    description="Returns matched/exception/pending review counts, total value, average confidence, confidence distribution, and match method breakdown.",
)
async def get_reconciliation_summary(
    run_id: uuid.UUID,
    x_organization_id: Optional[str] = Header(default=None, alias="X-Organization-Id"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ReconciliationSummaryResponse:
    # 1. Verify organization access
    target_org_id = await _resolve_org_id(current_user, db, x_organization_id)

    # 2. Fetch the run record
    stmt = select(ReconciliationRun).where(
        ReconciliationRun.id == run_id,
        ReconciliationRun.organization_id == target_org_id,
    )
    res = await db.execute(stmt)
    run = res.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Reconciliation run {run_id} not found.")

    # 3. Compute confidence distribution by transaction status
    dist_stmt = (
        select(
            Transaction.status,
            func.count(Transaction.id).label("count"),
            func.coalesce(func.sum(Transaction.amount), Decimal("0.00")).label("total_amount"),
            func.avg(Transaction.confidence).label("avg_confidence"),
        )
        .where(
            Transaction.reconciliation_run_id == run_id,
            Transaction.organization_id == target_org_id,
        )
        .group_by(Transaction.status)
    )
    dist_res = await db.execute(dist_stmt)
    distribution_rows = dist_res.all()

    confidence_distribution = [
        ConfidenceDistributionItem(
            status=row.status.value if hasattr(row.status, "value") else str(row.status),
            count=row.count,
            total_amount=row.total_amount or Decimal("0.00"),
            average_confidence=(
                round(Decimal(str(row.avg_confidence)), 4) if row.avg_confidence is not None else None
            ),
        )
        for row in distribution_rows
    ]

    # 4. Compute match method breakdown
    method_stmt = (
        select(
            Match.method,
            func.count(Match.id).label("count"),
        )
        .where(
            Match.reconciliation_run_id == run_id,
            Match.organization_id == target_org_id,
        )
        .group_by(Match.method)
    )
    method_res = await db.execute(method_stmt)
    match_method_breakdown = {
        (row.method.value if hasattr(row.method, "value") else str(row.method)): row.count
        for row in method_res.all()
    }

    return ReconciliationSummaryResponse(
        run_id=run.id,
        status=run.status,
        total_transactions=run.total_transactions,
        matched_count=run.matched_count,
        exception_count=run.exception_count,
        pending_review_count=run.pending_review_count,
        total_value_reconciled=run.total_value_reconciled,
        average_confidence=run.average_confidence,
        started_at=run.started_at,
        completed_at=run.completed_at,
        confidence_distribution=confidence_distribution,
        match_method_breakdown=match_method_breakdown,
    )


# ─── Internal helper ─────────────────────────────────────────────────────────
async def _fetch_run(
    run_id: uuid.UUID,
    current_user: User,
    db: AsyncSession,
    x_organization_id: Optional[str] = None,
) -> ReconcileRunResponse:
    stmt = select(ReconciliationRun).where(ReconciliationRun.id == run_id)
    res = await db.execute(stmt)
    run = res.scalar_one_or_none()

    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reconciliation run {run_id} not found.",
        )

    await db.refresh(run)

    # Verify user has access to this run's organization
    m_stmt = select(Membership).where(
        Membership.organization_id == run.organization_id,
        Membership.user_id == current_user.id,
    )
    m_res = await db.execute(m_stmt)
    if not m_res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You do not belong to the organization owning this run.",
        )

    return ReconcileRunResponse.model_validate(run)
