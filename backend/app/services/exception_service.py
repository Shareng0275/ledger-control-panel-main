import uuid
from decimal import Decimal
from typing import List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from app.models import (
    AuditLog,
    ExceptionStatus,
    Match,
    MatchMethod,
    ReconciliationException,
    ReconciliationRun,
    Transaction,
    TransactionSource,
    TransactionStatus,
)
from app.schemas.exception import BulkResolveResponse, ResolveExceptionResponse
from app.services.audit_service import AuditService
from app.utils.timezone import utc_now


class ExceptionService:
    """Business logic for exception review, manual resolution, and bulk triage."""

    @staticmethod
    async def get_exception(
        db: AsyncSession,
        exception_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> ReconciliationException:
        """Fetch a single exception with relations, enforcing tenant isolation."""
        stmt = (
            select(ReconciliationException)
            .where(
                ReconciliationException.id == exception_id,
                ReconciliationException.organization_id == organization_id,
            )
            .options(
                joinedload(ReconciliationException.transaction),
                joinedload(ReconciliationException.best_candidate_transaction),
            )
        )
        res = await db.execute(stmt)
        exc = res.scalar_one_or_none()
        if not exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Exception {exception_id} not found in this organization.",
            )
        return exc

    @staticmethod
    async def resolve_single_exception(
        db: AsyncSession,
        exception_id: uuid.UUID,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        action: str,
        candidate_id: Optional[uuid.UUID] = None,
        note: Optional[str] = None,
    ) -> ResolveExceptionResponse:
        """Resolve a single exception with match confirmation or rejection."""
        exc = await ExceptionService.get_exception(db, exception_id, organization_id)

        # Prevent duplicate submissions on already finalized exceptions
        if exc.status in {ExceptionStatus.RESOLVED, ExceptionStatus.REJECTED}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Exception {exception_id} is already finalized with status '{exc.status.value}'.",
            )

        clean_action = action.strip().lower()

        if clean_action in {"confirm_match", "confirm"}:
            target_candidate_id = candidate_id or exc.best_candidate_transaction_id
            if not target_candidate_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot confirm match without an associated candidate transaction.",
                )

            # Fetch transactions
            primary_tx = await db.get(Transaction, exc.transaction_id)
            candidate_tx = await db.get(Transaction, target_candidate_id)

            if not primary_tx or not candidate_tx or candidate_tx.organization_id != organization_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Candidate transaction not found or does not belong to this organization.",
                )

            # Partition into Statement and Ledger
            if primary_tx.source == TransactionSource.STATEMENT:
                stmt_tx, ledg_tx = primary_tx, candidate_tx
            else:
                stmt_tx, ledg_tx = candidate_tx, primary_tx

            # 1. Create Manual Match record
            match_rec = Match(
                id=uuid.uuid4(),
                organization_id=organization_id,
                reconciliation_run_id=exc.reconciliation_run_id,
                statement_transaction_id=stmt_tx.id,
                ledger_transaction_id=ledg_tx.id,
                method=MatchMethod.MANUAL,
                confidence=Decimal("1.0000"),
                score_details={
                    "rule": "Manual Analyst Resolution",
                    "resolved_by": str(user_id),
                    "note": note,
                    "previous_exception_id": str(exc.id),
                },
            )
            db.add(match_rec)

            # 2. Update Transactions
            stmt_tx.status = TransactionStatus.MATCHED
            stmt_tx.confidence = Decimal("1.0000")
            ledg_tx.status = TransactionStatus.MATCHED
            ledg_tx.confidence = Decimal("1.0000")

            # 3. Update Primary Exception
            prev_status = exc.status
            exc.status = ExceptionStatus.RESOLVED
            exc.resolution_action = "confirm_match"
            exc.resolved_by = user_id
            exc.resolved_at = utc_now()

            # 4. If candidate transaction has an open counterpart exception in same run, resolve it too
            counterpart_stmt = select(ReconciliationException).where(
                ReconciliationException.transaction_id == target_candidate_id,
                ReconciliationException.reconciliation_run_id == exc.reconciliation_run_id,
                ReconciliationException.status.in_([ExceptionStatus.OPEN, ExceptionStatus.REVIEWING]),
            )
            c_res = await db.execute(counterpart_stmt)
            counterpart_exc = c_res.scalar_one_or_none()
            if counterpart_exc:
                counterpart_exc.status = ExceptionStatus.RESOLVED
                counterpart_exc.resolution_action = "confirm_match"
                counterpart_exc.resolved_by = user_id
                counterpart_exc.resolved_at = utc_now()

            # 5. Update Run Statistics
            run = await db.get(ReconciliationRun, exc.reconciliation_run_id)
            if run:
                run.matched_count += 2
                if prev_status == ExceptionStatus.REVIEWING:
                    run.pending_review_count = max(0, run.pending_review_count - 1)
                else:
                    run.exception_count = max(0, run.exception_count - 1)
                run.total_value_reconciled += abs(stmt_tx.amount)

            # 6. Record Audit Log
            audit = AuditLog(
                id=uuid.uuid4(),
                organization_id=organization_id,
                actor_id=user_id,
                action="exception.resolved_match",
                entity_type="Exception",
                entity_id=exc.id,
                details={
                    "match_id": str(match_rec.id),
                    "statement_tx_id": str(stmt_tx.id),
                    "ledger_tx_id": str(ledg_tx.id),
                    "note": note,
                },
            )
            db.add(audit)
            await db.commit()

            return ResolveExceptionResponse(
                exception_id=exc.id,
                status=exc.status.value,
                message="Match confirmed and recorded successfully.",
                match_id=match_rec.id,
            )

        elif clean_action == "reject":
            prev_status = exc.status
            exc.status = ExceptionStatus.REJECTED
            exc.resolution_action = "reject"
            exc.resolved_by = user_id
            exc.resolved_at = utc_now()

            # Update run metrics if moving from review to rejected
            run = await db.get(ReconciliationRun, exc.reconciliation_run_id)
            if run and prev_status == ExceptionStatus.REVIEWING:
                run.pending_review_count = max(0, run.pending_review_count - 1)
                run.exception_count += 1

            # Audit Log
            audit = AuditLog(
                id=uuid.uuid4(),
                organization_id=organization_id,
                actor_id=user_id,
                action="exception.rejected",
                entity_type="Exception",
                entity_id=exc.id,
                details={"note": note, "reason": exc.reason_text},
            )
            db.add(audit)
            await db.commit()

            return ResolveExceptionResponse(
                exception_id=exc.id,
                status=exc.status.value,
                message="Exception marked as rejected.",
                match_id=None,
            )

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported resolution action '{action}'. Use 'confirm_match' or 'reject'.",
            )

    @staticmethod
    async def resolve_bulk_exceptions(
        db: AsyncSession,
        exception_ids: List[uuid.UUID],
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        action: str,
        note: Optional[str] = None,
    ) -> BulkResolveResponse:
        """Atomically resolve a list of exceptions in a single batch transaction."""
        results: List[ResolveExceptionResponse] = []
        errors: List[str] = []

        # Deduplicate incoming IDs
        unique_ids = list(dict.fromkeys(exception_ids))

        for exc_id in unique_ids:
            try:
                res = await ExceptionService.resolve_single_exception(
                    db=db,
                    exception_id=exc_id,
                    organization_id=organization_id,
                    user_id=user_id,
                    action=action,
                    note=note,
                )
                results.append(res)
            except HTTPException as hex:
                errors.append(f"Exception {exc_id}: {hex.detail}")
            except Exception as ex:
                errors.append(f"Exception {exc_id}: {str(ex)}")

        # Record bulk resolution audit log
        if results:
            await AuditService.log_event(
                db=db,
                organization_id=organization_id,
                actor_id=user_id,
                action="exception.bulk_resolved",
                entity_type="Exception",
                details={
                    "total_requested": len(unique_ids),
                    "resolved_count": len(results),
                    "failed_count": len(errors),
                    "action": action,
                    "note": note,
                },
                commit=True,
            )

        return BulkResolveResponse(
            total_requested=len(unique_ids),
            resolved_count=len(results),
            failed_count=len(errors),
            results=results,
            errors=errors,
        )
