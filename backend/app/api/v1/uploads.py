import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Request, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.db.session import get_db_session
from app.models import Membership, UploadType, User
from app.schemas.upload import UploadResponse
from app.services.ingestion_service import IngestionService

router = APIRouter(prefix="/uploads", tags=["Uploads"])


@router.post(
    "/statement",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload & Ingest Bank Statement CSV",
    description="Uploads a bank statement CSV, validates required columns and row integrity, normalizes financial values, and creates transactions.",
)
async def upload_statement(
    file: UploadFile,
    request: Request,
    x_organization_id: Optional[str] = Header(default=None, alias="X-Organization-Id"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> UploadResponse:
    # 1. Resolve Multi-Tenant Organization Scope
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
        # Fallback to user's primary organization membership
        m_stmt = select(Membership.organization_id).where(Membership.user_id == current_user.id).limit(1)
        res = await db.execute(m_stmt)
        target_org_id = res.scalar_one_or_none()

    if not target_org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active organization context found for this user.",
        )

    ip_address = request.client.host if request.client else None

    # 2. Process File Ingestion & Normalization
    return await IngestionService.process_upload(
        db=db,
        file=file,
        organization_id=target_org_id,
        upload_type=UploadType.STATEMENT,
        user=current_user,
        ip_address=ip_address,
    )


@router.post(
    "/ledger",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload & Ingest Internal/Gateway Ledger CSV",
    description="Uploads an internal or payment gateway ledger CSV, validates structure, normalizes financial values, and creates transactions.",
)
async def upload_ledger(
    file: UploadFile,
    request: Request,
    x_organization_id: Optional[str] = Header(default=None, alias="X-Organization-Id"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> UploadResponse:
    # 1. Resolve Multi-Tenant Organization Scope
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
        # Fallback to user's primary organization membership
        m_stmt = select(Membership.organization_id).where(Membership.user_id == current_user.id).limit(1)
        res = await db.execute(m_stmt)
        target_org_id = res.scalar_one_or_none()

    if not target_org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active organization context found for this user.",
        )

    ip_address = request.client.host if request.client else None

    # 2. Process File Ingestion & Normalization
    return await IngestionService.process_upload(
        db=db,
        file=file,
        organization_id=target_org_id,
        upload_type=UploadType.LEDGER,
        user=current_user,
        ip_address=ip_address,
    )
