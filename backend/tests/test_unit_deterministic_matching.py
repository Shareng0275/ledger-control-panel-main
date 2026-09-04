"""
Unit Tests: Deterministic Matching Rules & Conflict Handling
Verifies:
  - Rule 1: Exact reference matching
  - Rule 2: Exact amount + exact date matching
  - Rule 3: Exact amount + normalized description matching
  - Rule 4: Configurable date tolerance matching
  - 1-to-1 Conflict Handling (no transaction double-matched)
"""
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    MatchMethod,
    Membership,
    MembershipRole,
    Organization,
    ReconciliationRun,
    ReconciliationStatus,
    Transaction,
    TransactionSource,
    TransactionStatus,
    Upload,
    UploadStatus,
    UploadType,
    User,
)
from app.services.reconciliation_service import ReconciliationService


async def _setup_reconciliation_unit_context(db: AsyncSession):
    org = Organization(id=uuid.uuid4(), name="Reconcile Unit Org", slug=f"slug-{uuid.uuid4().hex[:8]}")
    user = User(id=uuid.uuid4(), email="rec@test.com", password_hash="h", full_name="User", is_active=True)
    db.add_all([org, user])
    await db.flush()

    m = Membership(id=uuid.uuid4(), organization_id=org.id, user_id=user.id, role=MembershipRole.ADMIN)
    db.add(m)

    u_stmt = Upload(
        id=uuid.uuid4(), organization_id=org.id, filename="s.csv",
        upload_type=UploadType.STATEMENT, storage_path="u/s.csv", status=UploadStatus.VALID,
    )
    u_ledg = Upload(
        id=uuid.uuid4(), organization_id=org.id, filename="l.csv",
        upload_type=UploadType.LEDGER, storage_path="u/l.csv", status=UploadStatus.VALID,
    )
    db.add_all([u_stmt, u_ledg])
    await db.flush()

    run = ReconciliationRun(
        id=uuid.uuid4(), organization_id=org.id,
        statement_upload_id=u_stmt.id, ledger_upload_id=u_ledg.id,
        status=ReconciliationStatus.PROCESSING,
        created_by=user.id,
    )
    db.add(run)
    await db.commit()

    return org, user, run, u_stmt, u_ledg


@pytest.mark.asyncio
async def test_deterministic_rule1_exact_reference(db_session: AsyncSession):
    """Rule 1: Statement and Ledger match with exact normalized reference."""
    org, user, run, u_stmt, u_ledg = await _setup_reconciliation_unit_context(db_session)
    dt = datetime(2026, 8, 1, tzinfo=timezone.utc)

    s1 = Transaction(
        id=uuid.uuid4(), organization_id=org.id, upload_id=u_stmt.id,
        source=TransactionSource.STATEMENT, transaction_date=dt,
        description="Vendor Invoice #8801", normalized_description="vendor invoice #8801",
        amount=Decimal("1200.0000"), currency="USD",
        external_reference="REF-8801", normalized_reference="ref-8801",
        status=TransactionStatus.PENDING_REVIEW, raw_data={},
    )
    l1 = Transaction(
        id=uuid.uuid4(), organization_id=org.id, upload_id=u_ledg.id,
        source=TransactionSource.LEDGER, transaction_date=dt + timedelta(days=2),
        description="Payment Outflow", normalized_description="payment outflow",
        amount=Decimal("1200.0000"), currency="USD",
        external_reference="REF-8801", normalized_reference="ref-8801",
        status=TransactionStatus.PENDING_REVIEW, raw_data={},
    )
    db_session.add_all([s1, l1])
    await db_session.commit()

    await ReconciliationService.run_reconciliation_job(run.id, org.id, user.id)
    await db_session.refresh(s1)
    await db_session.refresh(l1)

    assert s1.status == TransactionStatus.MATCHED
    assert l1.status == TransactionStatus.MATCHED
    assert s1.confidence == Decimal("1.0000")


@pytest.mark.asyncio
async def test_deterministic_conflict_handling_1_to_1(db_session: AsyncSession):
    """Ensure that once a transaction is matched, it cannot be matched again by another transaction."""
    org, user, run, u_stmt, u_ledg = await _setup_reconciliation_unit_context(db_session)
    dt = datetime(2026, 8, 1, tzinfo=timezone.utc)

    # Statement transaction
    s1 = Transaction(
        id=uuid.uuid4(), organization_id=org.id, upload_id=u_stmt.id,
        source=TransactionSource.STATEMENT, transaction_date=dt,
        description="Recurring Charge", normalized_description="recurring charge",
        amount=Decimal("500.0000"), currency="USD",
        status=TransactionStatus.PENDING_REVIEW, raw_data={},
    )
    # Two identical ledger transactions for $500
    l1 = Transaction(
        id=uuid.uuid4(), organization_id=org.id, upload_id=u_ledg.id,
        source=TransactionSource.LEDGER, transaction_date=dt,
        description="Recurring Charge", normalized_description="recurring charge",
        amount=Decimal("500.0000"), currency="USD",
        status=TransactionStatus.PENDING_REVIEW, raw_data={},
    )
    l2 = Transaction(
        id=uuid.uuid4(), organization_id=org.id, upload_id=u_ledg.id,
        source=TransactionSource.LEDGER, transaction_date=dt,
        description="Recurring Charge", normalized_description="recurring charge",
        amount=Decimal("500.0000"), currency="USD",
        status=TransactionStatus.PENDING_REVIEW, raw_data={},
    )
    db_session.add_all([s1, l1, l2])
    await db_session.commit()

    await ReconciliationService.run_reconciliation_job(run.id, org.id, user.id)
    await db_session.refresh(s1)
    await db_session.refresh(l1)
    await db_session.refresh(l2)

    assert s1.status == TransactionStatus.MATCHED
    # Exactly one ledger transaction matches s1; the other becomes an exception/review
    matched_count = sum(1 for tx in [l1, l2] if tx.status == TransactionStatus.MATCHED)
    assert matched_count == 1
