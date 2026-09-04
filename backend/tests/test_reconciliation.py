import io
import uuid
from datetime import datetime, timezone
from decimal import Decimal
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import create_access_token
from app.models import (
    AuditLog,
    Match,
    MatchMethod,
    Membership,
    MembershipRole,
    Organization,
    ReconciliationException,
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


async def setup_org_and_user(db_session: AsyncSession, name: str = "Test Org") -> tuple[Organization, User, str]:
    org = Organization(id=uuid.uuid4(), name=name, slug=f"slug-{uuid.uuid4().hex[:8]}")
    user = User(
        id=uuid.uuid4(),
        email=f"user-{uuid.uuid4().hex[:8]}@acme.com",
        password_hash="hash",
        full_name="Recon User",
        is_active=True,
    )
    db_session.add_all([org, user])
    await db_session.flush()

    m = Membership(
        id=uuid.uuid4(),
        organization_id=org.id,
        user_id=user.id,
        role=MembershipRole.ANALYST,
    )
    db_session.add(m)
    await db_session.commit()
    token = create_access_token(user_id=user.id)
    return org, user, token


@pytest.mark.asyncio
async def test_deterministic_reconciliation_full_pipeline(
    async_client: AsyncClient, db_session: AsyncSession
):
    """
    Test deterministic matching rules in priority order:
    1. Exact Reference Match (Conf: 1.0000)
    2. Exact Amount + Same Date (Conf: 0.9800)
    3. Exact Amount + Normalized Description (Conf: 0.9500)
    4. Exact Amount + Date Tolerance <= 2 days (Conf: 0.9000)
    5. Unmatched Records -> Exceptions created
    """
    org, user, token = await setup_org_and_user(db_session, "Pipeline Org")
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": str(org.id)}

    # Statement CSV: 5 rows
    # Row 1: Ref match (TXN-101, $1500)
    # Row 2: Same Date match (2026-08-15, $2400)
    # Row 3: Description match ("aws cloud hosting", $750, dates different)
    # Row 4: Date tolerance match ($320, stmt date 2026-08-10, ledger date 2026-08-12)
    # Row 5: Unmatched Statement ($9900)
    stmt_csv = (
        "Date,Description,Amount,Reference,Currency\n"
        "2026-08-01,Stripe Payout,1500.00,TXN-101,USD\n"
        "2026-08-15,Client Wire Transfer,2400.00,STMT-992,USD\n"
        "2026-08-05,AWS Cloud Hosting,750.00,STMT-771,USD\n"
        "2026-08-10,Office Supplies Store,320.00,STMT-881,USD\n"
        "2026-08-20,High Value Unmatched Deposit,9900.00,STMT-UNMATCHED,USD\n"
    )

    # Ledger CSV: 5 rows
    # Row 1: Ref match (TXN-101, $1500)
    # Row 2: Same Date match (2026-08-15, $2400, different ref LEDG-11)
    # Row 3: Description match ("AWS Cloud Hosting", $750, date 2026-08-25)
    # Row 4: Date tolerance match ($320, date 2026-08-12)
    # Row 5: Unmatched Ledger ($450)
    ledg_csv = (
        "Posting Date,Account Memo,Amount,Journal ID,Currency\n"
        "2026-08-01,Accounts Receivable Payout,1500.00,TXN-101,USD\n"
        "2026-08-15,Accounts Receivable Client,2400.00,LEDG-11,USD\n"
        "2026-08-25,AWS Cloud Hosting,750.00,LEDG-22,USD\n"
        "2026-08-12,Vendor Office Supplies,320.00,LEDG-33,USD\n"
        "2026-08-28,Miscellaneous Legal Expense,450.00,LEDG-44,USD\n"
    )

    # 1. Upload Statement
    res_s = await async_client.post(
        "/api/v1/uploads/statement",
        headers=headers,
        files={"file": ("stmt.csv", io.BytesIO(stmt_csv.encode("utf-8")), "text/csv")},
    )
    assert res_s.status_code == 201
    stmt_upload_id = uuid.UUID(res_s.json()["upload_id"])

    # 2. Upload Ledger
    res_l = await async_client.post(
        "/api/v1/uploads/ledger",
        headers=headers,
        files={"file": ("ledger.csv", io.BytesIO(ledg_csv.encode("utf-8")), "text/csv")},
    )
    assert res_l.status_code == 201
    ledg_upload_id = uuid.UUID(res_l.json()["upload_id"])

    # 3. Trigger Asynchronous Reconciliation Run
    res_run = await async_client.post(
        "/api/v1/reconcile/run",
        headers=headers,
        json={
            "statement_upload_id": str(stmt_upload_id),
            "ledger_upload_id": str(ledg_upload_id),
        },
    )
    assert res_run.status_code == 201
    run_data = res_run.json()
    assert "run_id" in run_data
    run_id = uuid.UUID(run_data["run_id"])

    # 4. Directly invoke matching worker to process synchronously in test context
    await ReconciliationService.run_reconciliation_job(
        run_id=run_id,
        organization_id=org.id,
        user_id=user.id,
        db_session=db_session,
    )

    # 5. Poll Status endpoint GET /api/v1/reconcile/{run_id}
    res_poll = await async_client.get(f"/api/v1/reconcile/{run_id}", headers=headers)
    assert res_poll.status_code == 200
    poll_data = res_poll.json()
    assert poll_data["status"] == "complete"
    assert poll_data["total_transactions"] == 10
    assert poll_data["matched_count"] == 8  # 4 pairs = 8 transactions
    assert poll_data["exception_count"] == 2  # 1 stmt + 1 ledger unmatched
    # Total reconciled value: 1500 + 2400 + 750 + 320 = 4970.00
    assert float(poll_data["total_value_reconciled"]) == 4970.00

    # 6. Verify Match records created in DB
    m_stmt = select(Match).where(Match.reconciliation_run_id == run_id)
    m_res = await db_session.execute(m_stmt)
    matches = list(m_res.scalars().all())
    assert len(matches) == 4
    assert all(m.method == MatchMethod.DETERMINISTIC for m in matches)

    confidences = {m.confidence for m in matches}
    assert Decimal("1.0000") in confidences
    assert Decimal("0.9800") in confidences
    assert Decimal("0.9500") in confidences
    assert Decimal("0.9000") in confidences

    # 7. Verify Exception records created
    e_stmt = select(ReconciliationException).where(ReconciliationException.reconciliation_run_id == run_id)
    e_res = await db_session.execute(e_stmt)
    exceptions = list(e_res.scalars().all())
    assert len(exceptions) == 2

    # High value exception check ($9900 > $5000 -> HIGH priority)
    e_high = next(e for e in exceptions if "Unmatched Statement" in e.reason_text)
    assert e_high.priority.value == "high"

    # 8. Verify Audit Log recorded
    audit_stmt = select(AuditLog).where(
        AuditLog.organization_id == org.id,
        AuditLog.entity_id == run_id,
    )
    a_res = await db_session.execute(audit_stmt)
    audit_logs = list(a_res.scalars().all())
    actions = {a.action for a in audit_logs}
    assert "reconciliation.started" in actions
    assert "reconciliation.completed" in actions


@pytest.mark.asyncio
async def test_reconciliation_conflict_prevention(
    async_client: AsyncClient, db_session: AsyncSession
):
    """Ensure that when multiple ledger rows have identical amount, one is matched and the other becomes an exception."""
    org, user, token = await setup_org_and_user(db_session, "Conflict Org")
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": str(org.id)}

    stmt_csv = "Date,Description,Amount,Reference\n2026-08-01,Single Statement Item,100.00,REF-1\n"
    ledg_csv = (
        "Date,Description,Amount,Reference\n"
        "2026-08-01,Ledger Item One,100.00,LEDG-1\n"
        "2026-08-01,Ledger Item Duplicate,100.00,LEDG-2\n"
    )

    res_s = await async_client.post("/api/v1/uploads/statement", headers=headers, files={"file": ("s.csv", io.BytesIO(stmt_csv.encode("utf-8")), "text/csv")})
    res_l = await async_client.post("/api/v1/uploads/ledger", headers=headers, files={"file": ("l.csv", io.BytesIO(ledg_csv.encode("utf-8")), "text/csv")})

    res_run = await async_client.post(
        "/api/v1/reconcile/run",
        headers=headers,
        json={
            "statement_upload_id": res_s.json()["upload_id"],
            "ledger_upload_id": res_l.json()["upload_id"],
        },
    )
    run_id = uuid.UUID(res_run.json()["run_id"])

    await ReconciliationService.run_reconciliation_job(run_id, org.id, user.id, db_session=db_session)

    res_poll = await async_client.get(f"/api/v1/reconcile/runs/{run_id}", headers=headers)
    data = res_poll.json()
    assert data["matched_count"] == 2  # 1 statement + 1 ledger
    assert data["exception_count"] == 1  # 2nd ledger became exception


@pytest.mark.asyncio
async def test_reconciliation_cross_tenant_isolation(
    async_client: AsyncClient, db_session: AsyncSession
):
    """Ensure user from Org A cannot access or trigger reconciliation for Org B."""
    org1, user1, token1 = await setup_org_and_user(db_session, "Tenant 1")
    org2, user2, token2 = await setup_org_and_user(db_session, "Tenant 2")

    # User 1 attempts to trigger reconciliation with Org 2's header
    headers = {"Authorization": f"Bearer {token1}", "X-Organization-Id": str(org2.id)}
    res = await async_client.post("/api/v1/reconcile/run", headers=headers, json={})
    assert res.status_code == 403
