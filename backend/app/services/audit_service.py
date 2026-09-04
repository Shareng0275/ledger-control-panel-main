import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.pagination import PaginationParams, paginate_select
from app.models import AuditLog, Membership, User
from app.schemas.audit import AuditEntry, AuditListResponse
from app.utils.timezone import utc_now

logger = logging.getLogger("ledger_control.audit")


class AuditService:
    """
    Centralized Append-Only Immutable Audit Trail Service.
    
    Guarantees:
    - Immutable append-only audit trail.
    - Zero update or delete operations on audit records.
    - Strict multi-tenant isolation on all reads and writes.
    - Standardized event schemas across all business services.
    """

    @classmethod
    async def log_event(
        cls,
        db: AsyncSession,
        organization_id: uuid.UUID,
        action: str,
        entity_type: str,
        actor_id: Optional[uuid.UUID] = None,
        entity_id: Optional[uuid.UUID] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        commit: bool = False,
    ) -> AuditLog:
        """
        Record an immutable append-only audit event.
        """
        audit = AuditLog(
            id=uuid.uuid4(),
            organization_id=organization_id,
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details or {},
            ip_address=ip_address,
            created_at=utc_now(),
        )
        db.add(audit)
        if commit:
            await db.commit()
        else:
            await db.flush()
        return audit

    # ─── Standardized Helper Methods ─────────────────────────────────────────

    @classmethod
    async def log_login(
        cls,
        db: AsyncSession,
        user: User,
        organization_id: Optional[uuid.UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """Record successful user authentication event."""
        # If organization_id is not specified, resolve primary organization
        target_org = organization_id
        if not target_org:
            m_stmt = select(Membership.organization_id).where(Membership.user_id == user.id).limit(1)
            res = await db.execute(m_stmt)
            target_org = res.scalar_one_or_none()

        if target_org:
            await cls.log_event(
                db=db,
                organization_id=target_org,
                actor_id=user.id,
                action="auth.login",
                entity_type="User",
                entity_id=user.id,
                details={"email": user.email, "user_agent": user_agent},
                ip_address=ip_address,
                commit=False,
            )

    @classmethod
    async def log_logout(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        organization_id: Optional[uuid.UUID] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        """Record user logout session revocation."""
        target_org = organization_id
        if not target_org:
            m_stmt = select(Membership.organization_id).where(Membership.user_id == user_id).limit(1)
            res = await db.execute(m_stmt)
            target_org = res.scalar_one_or_none()

        if target_org:
            await cls.log_event(
                db=db,
                organization_id=target_org,
                actor_id=user_id,
                action="auth.logout",
                entity_type="User",
                entity_id=user_id,
                details={"revoked": True},
                ip_address=ip_address,
                commit=False,
            )

    @classmethod
    async def log_upload_created(
        cls,
        db: AsyncSession,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        upload_id: uuid.UUID,
        filename: str,
        upload_type: str,
        row_count: int,
        ip_address: Optional[str] = None,
    ) -> None:
        """Record file upload creation and initial parsing."""
        await cls.log_event(
            db=db,
            organization_id=organization_id,
            actor_id=user_id,
            action="upload.created",
            entity_type="Upload",
            entity_id=upload_id,
            details={
                "filename": filename,
                "upload_type": upload_type,
                "row_count": row_count,
            },
            ip_address=ip_address,
            commit=False,
        )

    @classmethod
    async def log_upload_validation_failed(
        cls,
        db: AsyncSession,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        upload_id: uuid.UUID,
        filename: str,
        upload_type: str,
        validation_errors: Dict[str, Any],
        ip_address: Optional[str] = None,
    ) -> None:
        """Record upload validation errors (missing headers, corrupt rows)."""
        await cls.log_event(
            db=db,
            organization_id=organization_id,
            actor_id=user_id,
            action="upload.validation_failed",
            entity_type="Upload",
            entity_id=upload_id,
            details={
                "filename": filename,
                "upload_type": upload_type,
                "validation_errors": validation_errors,
            },
            ip_address=ip_address,
            commit=False,
        )

    @classmethod
    async def log_reconciliation_started(
        cls,
        db: AsyncSession,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        run_id: uuid.UUID,
        statement_upload_id: Optional[uuid.UUID],
        ledger_upload_id: Optional[uuid.UUID],
    ) -> None:
        """Record reconciliation run dispatch."""
        await cls.log_event(
            db=db,
            organization_id=organization_id,
            actor_id=user_id,
            action="reconciliation.started",
            entity_type="ReconciliationRun",
            entity_id=run_id,
            details={
                "statement_upload_id": str(statement_upload_id) if statement_upload_id else None,
                "ledger_upload_id": str(ledger_upload_id) if ledger_upload_id else None,
            },
            commit=False,
        )

    @classmethod
    async def log_reconciliation_completed(
        cls,
        db: AsyncSession,
        organization_id: uuid.UUID,
        run_id: uuid.UUID,
        matched_count: int,
        exception_count: int,
        pending_review_count: int,
        total_value_reconciled: Any,
        user_id: Optional[uuid.UUID] = None,
    ) -> None:
        """Record reconciliation run completion and metrics."""
        await cls.log_event(
            db=db,
            organization_id=organization_id,
            actor_id=user_id,
            action="reconciliation.completed",
            entity_type="ReconciliationRun",
            entity_id=run_id,
            details={
                "matched_count": matched_count,
                "exception_count": exception_count,
                "pending_review_count": pending_review_count,
                "total_value_reconciled": str(total_value_reconciled),
            },
            commit=False,
        )

    @classmethod
    async def log_reconciliation_failed(
        cls,
        db: AsyncSession,
        organization_id: uuid.UUID,
        run_id: uuid.UUID,
        error_message: str,
        user_id: Optional[uuid.UUID] = None,
    ) -> None:
        """Record reconciliation failure."""
        await cls.log_event(
            db=db,
            organization_id=organization_id,
            actor_id=user_id,
            action="reconciliation.failed",
            entity_type="ReconciliationRun",
            entity_id=run_id,
            details={"error_message": error_message},
            commit=False,
        )

    # ─── Query / List Audit Trail ─────────────────────────────────────────────

    @classmethod
    async def list_audit_trail(
        cls,
        db: AsyncSession,
        organization_id: uuid.UUID,
        pagination: PaginationParams,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        action: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[uuid.UUID] = None,
        run_id: Optional[uuid.UUID] = None,
    ) -> AuditListResponse:
        """
        Queries immutable audit records chronologically with pagination and filters.
        Strictly scopes to organization_id.
        """
        query = (
            select(AuditLog)
            .where(AuditLog.organization_id == organization_id)
            .options(selectinload(AuditLog.actor))
        )

        # Filters
        if start_date:
            query = query.where(AuditLog.created_at >= start_date)
        if end_date:
            query = query.where(AuditLog.created_at <= end_date)
        if action:
            query = query.where(AuditLog.action.ilike(f"%{action.strip()}%"))
        if entity_type:
            query = query.where(AuditLog.entity_type.ilike(f"%{entity_type.strip()}%"))
        if entity_id:
            query = query.where(AuditLog.entity_id == entity_id)
        if run_id:
            query = query.where(
                or_(
                    AuditLog.entity_id == run_id,
                    AuditLog.details["reconciliation_run_id"].as_string() == str(run_id),
                )
            )

        items, total, total_pages = await paginate_select(
            db=db,
            select_query=query,
            page_params=pagination,
            sort_column=AuditLog.created_at,
            sort_order="desc",
        )

        entries = []
        for item in items:
            actor_name = item.actor.full_name if item.actor else "System"
            entries.append(
                AuditEntry(
                    id=item.id,
                    created_at=item.created_at,
                    actor=actor_name,
                    actor_id=item.actor_id,
                    action=item.action,
                    entity_type=item.entity_type,
                    entity_id=item.entity_id,
                    details=item.details,
                    ip_address=item.ip_address,
                )
            )

        return AuditListResponse(
            items=entries,
            entries=entries,
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
            total_pages=total_pages,
            has_next=pagination.page < total_pages,
            has_prev=pagination.page > 1,
        )
