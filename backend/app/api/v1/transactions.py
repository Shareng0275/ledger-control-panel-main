import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.core.pagination import PaginationParams, get_pagination_params, paginate_select
from app.db.session import get_db_session
from app.models import (
    AuditLog,
    Match,
    Membership,
    Transaction,
    TransactionSource,
    TransactionStatus,
    User,
)
from app.schemas.transaction import (
    AuditEntryDTO,
    MatchInfoDTO,
    TransactionDetailResponse,
    TransactionListResponse,
    TransactionResponse,
)

router = APIRouter(prefix="/transactions", tags=["Transactions"])

# Whitelist allowed sorting columns to prevent SQL injection
SORTABLE_COLUMNS = {
    "transaction_date": Transaction.transaction_date,
    "date": Transaction.transaction_date,
    "amount": Transaction.amount,
    "status": Transaction.status,
    "source": Transaction.source,
    "confidence": Transaction.confidence,
    "created_at": Transaction.created_at,
}


@router.get(
    "",
    response_model=TransactionListResponse,
    status_code=status.HTTP_200_OK,
    summary="List & Filter Transactions",
    description="Retrieve paginated transactions with safe server-side search, filtering, and whitelisted sorting.",
)
async def list_transactions(
    run_id: Optional[uuid.UUID] = Query(default=None, alias="run_id", description="Filter by reconciliation run"),
    source: Optional[TransactionSource] = Query(default=None, description="Statement or Ledger source"),
    status_filter: Optional[TransactionStatus] = Query(default=None, alias="status", description="Matched, Exception, or Pending Review"),
    search: Optional[str] = Query(default=None, max_length=100, description="Search description or reference"),
    start_date: Optional[datetime] = Query(default=None, description="Filter transactions after this date"),
    end_date: Optional[datetime] = Query(default=None, description="Filter transactions before this date"),
    min_amount: Optional[Decimal] = Query(default=None, ge=0, description="Minimum transaction amount"),
    max_amount: Optional[Decimal] = Query(default=None, ge=0, description="Maximum transaction amount"),
    sort_by: str = Query(default="transaction_date", description="Field to sort by"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$", description="Sort direction (asc/desc)"),
    pagination: PaginationParams = Depends(get_pagination_params),
    x_organization_id: Optional[str] = Header(default=None, alias="X-Organization-Id"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> TransactionListResponse:
    # 1. Resolve Multi-Tenant Organization Scope
    target_org_id: Optional[uuid.UUID] = None
    if x_organization_id:
        try:
            target_org_id = uuid.UUID(x_organization_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid 'X-Organization-Id' header format. Must be a UUID.",
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
        m_stmt = select(Membership.organization_id).where(Membership.user_id == current_user.id).limit(1)
        m_res = await db.execute(m_stmt)
        target_org_id = m_res.scalar_one_or_none()
        if not target_org_id:
            return TransactionListResponse(
                items=[],
                transactions=[],
                total=0,
                page=pagination.page,
                page_size=pagination.page_size,
                total_pages=1,
                has_next=False,
                has_prev=False,
            )

    # 2. Build Base Query with strict Tenant Boundary
    query = select(Transaction).where(Transaction.organization_id == target_org_id)

    # 3. Apply Filters
    if run_id:
        query = query.where(Transaction.reconciliation_run_id == run_id)
    if source:
        query = query.where(Transaction.source == source)
    if status_filter:
        query = query.where(Transaction.status == status_filter)
    if start_date:
        query = query.where(Transaction.transaction_date >= start_date)
    if end_date:
        query = query.where(Transaction.transaction_date <= end_date)
    if min_amount is not None:
        query = query.where(Transaction.amount >= min_amount)
    if max_amount is not None:
        query = query.where(Transaction.amount <= max_amount)

    # 4. Safe Text Search (Avoid injection, case-insensitive)
    if search:
        search_term = f"%{search.strip()}%"
        query = query.where(
            or_(
                Transaction.description.ilike(search_term),
                Transaction.external_reference.ilike(search_term),
            )
        )

    # 5. Whitelisted Sorting (Default to transaction_date desc)
    sort_column = SORTABLE_COLUMNS.get(sort_by.lower(), Transaction.transaction_date)

    # 6. Execute Paginated Query
    items, total, total_pages = await paginate_select(
        db=db,
        select_query=query,
        page_params=pagination,
        sort_column=sort_column,
        sort_order=sort_order,
    )

    tx_dtos = [TransactionResponse.model_validate(item) for item in items]

    return TransactionListResponse(
        items=tx_dtos,
        transactions=tx_dtos,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=total_pages,
        has_next=pagination.page < total_pages,
        has_prev=pagination.page > 1,
    )


@router.get(
    "/{transaction_id}",
    response_model=TransactionDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Transaction Detail",
    description="Retrieve full transaction detail including match information and audit history.",
)
async def get_transaction_detail(
    transaction_id: uuid.UUID,
    x_organization_id: Optional[str] = Header(default=None, alias="X-Organization-Id"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> TransactionDetailResponse:
    # 1. Resolve target org
    target_org_id: Optional[uuid.UUID] = None
    if x_organization_id:
        target_org_id = uuid.UUID(x_organization_id)
    else:
        m_stmt = select(Membership.organization_id).where(Membership.user_id == current_user.id).limit(1)
        res = await db.execute(m_stmt)
        target_org_id = res.scalar_one_or_none()

    if not target_org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No active organization.")

    # Verify membership
    m_check = select(Membership).where(
        Membership.user_id == current_user.id,
        Membership.organization_id == target_org_id,
    )
    m_res = await db.execute(m_check)
    if not m_res.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    # 2. Fetch Transaction
    tx_stmt = select(Transaction).where(
        Transaction.id == transaction_id,
        Transaction.organization_id == target_org_id,
    )
    tx_res = await db.execute(tx_stmt)
    tx = tx_res.scalar_one_or_none()
    if not tx:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found.")

    # 3. Build Match Info (if matched)
    match_info = None
    if tx.status == TransactionStatus.MATCHED:
        match_q = select(Match).where(
            Match.reconciliation_run_id == tx.reconciliation_run_id,
            or_(
                Match.statement_transaction_id == tx.id,
                Match.ledger_transaction_id == tx.id,
            ),
        )
        match_res = await db.execute(match_q)
        match_rec = match_res.scalar_one_or_none()
        if match_rec:
            # Determine counterpart
            counterpart_id = (
                match_rec.ledger_transaction_id
                if match_rec.statement_transaction_id == tx.id
                else match_rec.statement_transaction_id
            )
            counterpart = await db.get(Transaction, counterpart_id) if counterpart_id else None
            match_info = MatchInfoDTO(
                id=match_rec.id,
                method=match_rec.method,
                confidence=match_rec.confidence,
                score_details=match_rec.score_details,
                counterpart_transaction_id=counterpart.id if counterpart else None,
                counterpart_description=counterpart.description if counterpart else None,
                counterpart_amount=counterpart.amount if counterpart else None,
                counterpart_date=counterpart.transaction_date if counterpart else None,
            )

    # 4. Fetch Audit History for this transaction
    audit_q = select(AuditLog).where(
        AuditLog.organization_id == target_org_id,
        AuditLog.entity_id == tx.id,
    ).order_by(AuditLog.created_at.desc()).limit(20)
    audit_res = await db.execute(audit_q)
    audit_logs = list(audit_res.scalars().all())

    audit_dtos = [
        AuditEntryDTO(
            id=a.id,
            action=a.action,
            actor_id=a.actor_id,
            details=a.details,
            created_at=a.created_at,
        )
        for a in audit_logs
    ]

    return TransactionDetailResponse(
        id=tx.id,
        transaction_date=tx.transaction_date,
        description=tx.description,
        normalized_description=tx.normalized_description,
        amount=tx.amount,
        currency=tx.currency,
        source=tx.source,
        external_reference=tx.external_reference,
        normalized_reference=tx.normalized_reference,
        status=tx.status,
        confidence=tx.confidence,
        reconciliation_run_id=tx.reconciliation_run_id,
        created_at=tx.created_at,
        match_info=match_info,
        audit_history=audit_dtos,
    )
