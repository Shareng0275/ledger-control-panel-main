import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set, Tuple
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.database import async_session_factory
from app.core.logging import logger
from app.models import (
    AuditLog,
    ExceptionPriority,
    ExceptionStatus,
    Match,
    MatchMethod,
    ReconciliationException,
    ReconciliationRun,
    ReconciliationStatus,
    Transaction,
    TransactionSource,
    TransactionStatus,
    Upload,
    UploadStatus,
    UploadType,
)
from app.services.fuzzy_matcher import FuzzyMatcher, FuzzyScoreBreakdown
from app.utils.timezone import utc_now


class ReconciliationService:
    """Deterministic and Intelligent Fuzzy financial reconciliation service."""

    @staticmethod
    async def validate_uploads(
        db: AsyncSession,
        organization_id: uuid.UUID,
        statement_upload_id: Optional[uuid.UUID] = None,
        ledger_upload_id: Optional[uuid.UUID] = None,
    ) -> Tuple[Upload, Upload]:
        """Validate that uploads exist, belong to the organization, and have valid types and status."""
        stmt_upload: Optional[Upload] = None
        ledg_upload: Optional[Upload] = None

        if statement_upload_id:
            stmt_res = await db.execute(
                select(Upload).where(
                    Upload.id == statement_upload_id,
                    Upload.organization_id == organization_id,
                )
            )
            stmt_upload = stmt_res.scalar_one_or_none()
            if not stmt_upload:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Statement upload {statement_upload_id} not found in this organization.",
                )
            if stmt_upload.upload_type != UploadType.STATEMENT:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Upload {statement_upload_id} is of type {stmt_upload.upload_type.value}, expected 'statement'.",
                )
        else:
            # Auto-discover most recent valid statement upload
            stmt_res = await db.execute(
                select(Upload)
                .where(
                    Upload.organization_id == organization_id,
                    Upload.upload_type == UploadType.STATEMENT,
                    Upload.status == UploadStatus.VALID,
                )
                .order_by(Upload.created_at.desc())
                .limit(1)
            )
            stmt_upload = stmt_res.scalar_one_or_none()

        if ledger_upload_id:
            ledg_res = await db.execute(
                select(Upload).where(
                    Upload.id == ledger_upload_id,
                    Upload.organization_id == organization_id,
                )
            )
            ledg_upload = ledg_res.scalar_one_or_none()
            if not ledg_upload:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Ledger upload {ledger_upload_id} not found in this organization.",
                )
            if ledg_upload.upload_type != UploadType.LEDGER:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Upload {ledger_upload_id} is of type {ledg_upload.upload_type.value}, expected 'ledger'.",
                )
        else:
            # Auto-discover most recent valid ledger upload
            ledg_res = await db.execute(
                select(Upload)
                .where(
                    Upload.organization_id == organization_id,
                    Upload.upload_type == UploadType.LEDGER,
                    Upload.status == UploadStatus.VALID,
                )
                .order_by(Upload.created_at.desc())
                .limit(1)
            )
            ledg_upload = ledg_res.scalar_one_or_none()

        if not stmt_upload or not ledg_upload:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Both a valid bank statement and general ledger upload are required to start reconciliation.",
            )

        return stmt_upload, ledg_upload

    @staticmethod
    async def create_run(
        db: AsyncSession,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        statement_upload_id: uuid.UUID,
        ledger_upload_id: uuid.UUID,
    ) -> ReconciliationRun:
        """Initialize and persist a new ReconciliationRun record."""
        run = ReconciliationRun(
            id=uuid.uuid4(),
            organization_id=organization_id,
            statement_upload_id=statement_upload_id,
            ledger_upload_id=ledger_upload_id,
            status=ReconciliationStatus.PROCESSING,
            total_transactions=0,
            matched_count=0,
            exception_count=0,
            pending_review_count=0,
            total_value_reconciled=Decimal("0.0000"),
            average_confidence=None,
            created_by=user_id,
            started_at=utc_now(),
        )
        db.add(run)

        audit = AuditLog(
            id=uuid.uuid4(),
            organization_id=organization_id,
            actor_id=user_id,
            action="reconciliation.started",
            entity_type="ReconciliationRun",
            entity_id=run.id,
            details={
                "statement_upload_id": str(statement_upload_id),
                "ledger_upload_id": str(ledger_upload_id),
            },
        )
        db.add(audit)
        await db.commit()
        await db.refresh(run)
        return run

    @staticmethod
    async def run_reconciliation_job(
        run_id: uuid.UUID,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        db_session: Optional[AsyncSession] = None,
    ) -> None:
        """Asynchronous execution worker for deterministic and fuzzy reconciliation pipeline."""
        if db_session is not None:
            await ReconciliationService._execute_reconciliation(db_session, run_id, organization_id, user_id)
        else:
            async with async_session_factory() as db:
                await ReconciliationService._execute_reconciliation(db, run_id, organization_id, user_id)

    @staticmethod
    async def _execute_reconciliation(
        db: AsyncSession,
        run_id: uuid.UUID,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        try:
            # 1. Fetch Run
            run_stmt = select(ReconciliationRun).where(ReconciliationRun.id == run_id)
            run_res = await db.execute(run_stmt)
            run = run_res.scalar_one_or_none()
            if not run:
                logger.error(f"ReconciliationRun {run_id} not found.")
                return

            if run.status in {ReconciliationStatus.COMPLETE, ReconciliationStatus.FAILED}:
                logger.info(f"ReconciliationRun {run_id} is already in state {run.status.value}, skipping.")
                return

            # 2. Fetch Statement and Ledger Transactions
            stmt_query = select(Transaction).where(
                Transaction.upload_id == run.statement_upload_id,
                Transaction.organization_id == organization_id,
            )
            stmt_res = await db.execute(stmt_query)
            statement_txs: List[Transaction] = list(stmt_res.scalars().all())

            ledg_query = select(Transaction).where(
                Transaction.upload_id == run.ledger_upload_id,
                Transaction.organization_id == organization_id,
            )
            ledg_res = await db.execute(ledg_query)
            ledger_txs: List[Transaction] = list(ledg_res.scalars().all())

            # Associate all transactions with this reconciliation run
            for tx in statement_txs + ledger_txs:
                tx.reconciliation_run_id = run.id

            # 3. Matching Engine (Deterministic First, Followed by Intelligent Fuzzy)
            matched_statement_ids: Set[uuid.UUID] = set()
            matched_ledger_ids: Set[uuid.UUID] = set()
            matches_to_create: List[Match] = []

            # Helper to match a pair
            def match_pair(
                s_tx: Transaction,
                l_tx: Transaction,
                method: MatchMethod,
                confidence: Decimal,
                rule_name: str,
                score_details: Optional[Dict[str, Any]] = None,
            ) -> None:
                matched_statement_ids.add(s_tx.id)
                matched_ledger_ids.add(l_tx.id)
                s_tx.status = TransactionStatus.MATCHED
                s_tx.confidence = confidence
                l_tx.status = TransactionStatus.MATCHED
                l_tx.confidence = confidence

                details = score_details or {
                    "rule": rule_name,
                    "statement_amount": str(s_tx.amount),
                    "ledger_amount": str(l_tx.amount),
                    "statement_date": s_tx.transaction_date.isoformat(),
                    "ledger_date": l_tx.transaction_date.isoformat(),
                }

                match_rec = Match(
                    id=uuid.uuid4(),
                    organization_id=organization_id,
                    reconciliation_run_id=run.id,
                    statement_transaction_id=s_tx.id,
                    ledger_transaction_id=l_tx.id,
                    method=method,
                    confidence=confidence,
                    score_details=details,
                )
                matches_to_create.append(match_rec)

            # ==========================================
            # PHASE 1: DETERMINISTIC MATCHING (Highest Priority)
            # ==========================================

            # Rule 1: Exact Normalized Reference Match
            for s in statement_txs:
                if s.id in matched_statement_ids or not s.normalized_reference:
                    continue
                for l in ledger_txs:
                    if l.id in matched_ledger_ids or not l.normalized_reference:
                        continue
                    if s.normalized_reference == l.normalized_reference and s.amount == l.amount:
                        match_pair(s, l, MatchMethod.DETERMINISTIC, Decimal("1.0000"), "Exact Reference Match")
                        break

            # Rule 2: Exact Amount + Same Transaction Date
            for s in statement_txs:
                if s.id in matched_statement_ids:
                    continue
                for l in ledger_txs:
                    if l.id in matched_ledger_ids:
                        continue
                    if s.amount == l.amount and s.transaction_date.date() == l.transaction_date.date():
                        match_pair(s, l, MatchMethod.DETERMINISTIC, Decimal("0.9800"), "Exact Amount and Date")
                        break

            # Rule 3: Exact Amount + Normalized Description Match
            for s in statement_txs:
                if s.id in matched_statement_ids:
                    continue
                for l in ledger_txs:
                    if l.id in matched_ledger_ids:
                        continue
                    if s.amount == l.amount:
                        s_desc = s.normalized_description or ""
                        l_desc = l.normalized_description or ""
                        if s_desc and l_desc and (s_desc == l_desc or s_desc in l_desc or l_desc in s_desc):
                            match_pair(s, l, MatchMethod.DETERMINISTIC, Decimal("0.9500"), "Exact Amount and Description")
                            break

            # Rule 4: Exact Amount + Date Tolerance (within ±2 days)
            for s in statement_txs:
                if s.id in matched_statement_ids:
                    continue
                for l in ledger_txs:
                    if l.id in matched_ledger_ids:
                        continue
                    if s.amount == l.amount:
                        delta_days = abs((s.transaction_date.date() - l.transaction_date.date()).days)
                        if delta_days <= 2:
                            match_pair(s, l, MatchMethod.DETERMINISTIC, Decimal("0.9000"), f"Date Tolerance (±{delta_days}d)")
                            break

            # ==========================================
            # PHASE 2: INTELLIGENT FUZZY MATCHING (Unmatched Only)
            # ==========================================
            unmatched_stmt = [s for s in statement_txs if s.id not in matched_statement_ids]
            unmatched_ledg = [l for l in ledger_txs if l.id not in matched_ledger_ids]

            candidate_pairs = FuzzyMatcher.generate_candidate_pairs(unmatched_stmt, unmatched_ledg)

            auto_thresh = Decimal(str(settings.FUZZY_AUTO_MATCH_THRESHOLD))
            for s, l, score in candidate_pairs:
                if s.id not in matched_statement_ids and l.id not in matched_ledger_ids:
                    if score.overall_confidence >= auto_thresh:
                        match_pair(
                            s,
                            l,
                            MatchMethod.FUZZY,
                            score.overall_confidence,
                            "Intelligent Fuzzy Match",
                            score_details=score.to_dict(),
                        )

            # ==========================================
            # PHASE 3: TRIAGE & EXCEPTION GENERATION (Review vs Open Exception)
            # ==========================================
            exceptions_to_create: List[ReconciliationException] = []
            review_thresh = Decimal(str(settings.FUZZY_REVIEW_THRESHOLD))

            def get_best_candidate(tx_id: uuid.UUID, is_statement: bool) -> Optional[Tuple[Transaction, FuzzyScoreBreakdown]]:
                best = None
                for s, l, sc in candidate_pairs:
                    if is_statement and s.id == tx_id and l.id not in matched_ledger_ids:
                        if best is None or sc.overall_confidence > best[1].overall_confidence:
                            best = (l, sc)
                    elif not is_statement and l.id == tx_id and s.id not in matched_statement_ids:
                        if best is None or sc.overall_confidence > best[1].overall_confidence:
                            best = (s, sc)
                return best

            # Triage Statement Transactions
            for s in statement_txs:
                if s.id not in matched_statement_ids:
                    best = get_best_candidate(s.id, is_statement=True)
                    if best and best[1].overall_confidence >= review_thresh:
                        candidate_tx, score = best
                        s.status = TransactionStatus.PENDING_REVIEW
                        s.confidence = score.overall_confidence

                        exc = ReconciliationException(
                            id=uuid.uuid4(),
                            organization_id=organization_id,
                            reconciliation_run_id=run.id,
                            transaction_id=s.id,
                            best_candidate_transaction_id=candidate_tx.id,
                            reason_text=f"Review Required ({score.explanation})",
                            priority=ExceptionPriority.HIGH if abs(s.amount) >= Decimal("5000.00") else ExceptionPriority.MEDIUM,
                            status=ExceptionStatus.REVIEWING,
                        )
                        exceptions_to_create.append(exc)
                    else:
                        s.status = TransactionStatus.EXCEPTION
                        s.confidence = best[1].overall_confidence if best else None
                        candidate_id = best[0].id if best else None
                        reason_msg = f"Unmatched Statement: No matching general ledger entry found for {s.currency} {s.amount}."
                        if best:
                            reason_msg += f" Closest candidate: {best[1].explanation}"

                        exc = ReconciliationException(
                            id=uuid.uuid4(),
                            organization_id=organization_id,
                            reconciliation_run_id=run.id,
                            transaction_id=s.id,
                            best_candidate_transaction_id=candidate_id,
                            reason_text=reason_msg,
                            priority=ExceptionPriority.HIGH if abs(s.amount) >= Decimal("5000.00") else ExceptionPriority.MEDIUM,
                            status=ExceptionStatus.OPEN,
                        )
                        exceptions_to_create.append(exc)

            # Triage Ledger Transactions
            for l in ledger_txs:
                if l.id not in matched_ledger_ids:
                    best = get_best_candidate(l.id, is_statement=False)
                    if best and best[1].overall_confidence >= review_thresh:
                        candidate_tx, score = best
                        l.status = TransactionStatus.PENDING_REVIEW
                        l.confidence = score.overall_confidence

                        exc = ReconciliationException(
                            id=uuid.uuid4(),
                            organization_id=organization_id,
                            reconciliation_run_id=run.id,
                            transaction_id=l.id,
                            best_candidate_transaction_id=candidate_tx.id,
                            reason_text=f"Review Required ({score.explanation})",
                            priority=ExceptionPriority.HIGH if abs(l.amount) >= Decimal("5000.00") else ExceptionPriority.MEDIUM,
                            status=ExceptionStatus.REVIEWING,
                        )
                        exceptions_to_create.append(exc)
                    else:
                        l.status = TransactionStatus.EXCEPTION
                        l.confidence = best[1].overall_confidence if best else None
                        candidate_id = best[0].id if best else None
                        reason_msg = f"Unmatched Ledger: No matching bank statement entry found for {l.currency} {l.amount}."
                        if best:
                            reason_msg += f" Closest candidate: {best[1].explanation}"

                        exc = ReconciliationException(
                            id=uuid.uuid4(),
                            organization_id=organization_id,
                            reconciliation_run_id=run.id,
                            transaction_id=l.id,
                            best_candidate_transaction_id=candidate_id,
                            reason_text=reason_msg,
                            priority=ExceptionPriority.HIGH if abs(l.amount) >= Decimal("5000.00") else ExceptionPriority.MEDIUM,
                            status=ExceptionStatus.OPEN,
                        )
                        exceptions_to_create.append(exc)

            # 4. Persist Matches and Exceptions
            if matches_to_create:
                db.add_all(matches_to_create)
            if exceptions_to_create:
                db.add_all(exceptions_to_create)

            # 5. Aggregate Run Statistics
            total_count = len(statement_txs) + len(ledger_txs)
            matched_count = len(matched_statement_ids) + len(matched_ledger_ids)
            pending_review_count = sum(1 for tx in (statement_txs + ledger_txs) if tx.status == TransactionStatus.PENDING_REVIEW)
            exception_count = sum(1 for tx in (statement_txs + ledger_txs) if tx.status == TransactionStatus.EXCEPTION)

            total_value = sum((abs(s.amount) for s in statement_txs if s.id in matched_statement_ids), Decimal("0.0000"))

            avg_conf = None
            if matches_to_create:
                avg_conf = (sum((m.confidence for m in matches_to_create), Decimal("0.0000")) / len(matches_to_create)).quantize(Decimal("0.0001"))

            run.total_transactions = total_count
            run.matched_count = matched_count
            run.pending_review_count = pending_review_count
            run.exception_count = exception_count
            run.total_value_reconciled = total_value.quantize(Decimal("0.01"))
            run.average_confidence = avg_conf
            run.status = ReconciliationStatus.COMPLETE
            run.completed_at = utc_now()

            # Audit Log completion
            audit_complete = AuditLog(
                id=uuid.uuid4(),
                organization_id=organization_id,
                actor_id=user_id,
                action="reconciliation.completed",
                entity_type="ReconciliationRun",
                entity_id=run.id,
                details={
                    "total_transactions": total_count,
                    "matched_count": matched_count,
                    "pending_review_count": pending_review_count,
                    "exception_count": exception_count,
                    "total_value_reconciled": str(total_value),
                    "average_confidence": str(avg_conf) if avg_conf else None,
                },
            )
            db.add(audit_complete)

            await db.commit()
            logger.info(
                f"ReconciliationRun {run.id} completed: {matched_count}/{total_count} matched, "
                f"{pending_review_count} review, {exception_count} exceptions."
            )

        except Exception as exc:
            logger.exception(f"Error during ReconciliationRun {run_id}: {exc}")
            await db.rollback()
            try:
                f_res = await db.execute(
                    select(ReconciliationRun).where(ReconciliationRun.id == run_id)
                )
                failed_run = f_res.scalar_one_or_none()
                if failed_run:
                    failed_run.status = ReconciliationStatus.FAILED
                    failed_run.error_message = str(exc)
                    failed_run.completed_at = utc_now()

                    audit_fail = AuditLog(
                        id=uuid.uuid4(),
                        organization_id=organization_id,
                        actor_id=user_id,
                        action="reconciliation.failed",
                        entity_type="ReconciliationRun",
                        entity_id=run_id,
                        details={"error": str(exc)},
                    )
                    db.add(audit_fail)
                    await db.commit()
            except Exception as inner_exc:
                logger.error(f"Failed to record failure state for run {run_id}: {inner_exc}")
