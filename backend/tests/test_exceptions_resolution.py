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
    ExceptionPriority,
    ExceptionStatus,
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


async def setup_test_context(db: AsyncSession, org_name: str = "Exception Org"):
    org = Organization(id=uuid.uuid4(), name=org_name, slug=f"slug-{uuid.uuid4().hex[:8]}")
    user = User(
        id=uuid.uuid4(),
        email=f"analyst-{uuid.uuid4().hex[:8]}@acme.com",
        password_hash="hash",
        full_name="Analyst User",
        is_active=True,
    )
    db.add_all([org, user])
    await db.flush()

    m = Membership(
        id=uuid.uuid4(),
        organization_id=org.id,
        user_id=user.id,
        role=MembershipRole.ANALYST,
    )
    db.add(m)

    u_stmt = Upload(
        id=uuid.uuid4(),
        organization_id=org.id,
        filename="stmt.csv",
        upload_type=UploadType.STATEMENT,
        storage_path="uploads/stmt.csv",
        status=UploadStatus.VALID,
    )
    u_ledg = Upload(
        id=uuid.uuid4(),
        organization_id=org.id,
        filename="ledg.csv",
        upload_type=UploadType.LEDGER,
        storage_path="uploads/ledg.csv",
        status=UploadStatus.VALID,
    )
    db.add_all([u_stmt, u_ledg])
    await db.flush()

    run = ReconciliationRun(
        id=uuid.uuid4(),
        organization_id=org.id,
        statement_upload_id=u_stmt.id,
        ledger_upload_id=u_ledg.id,
        status=ReconciliationStatus.COMPLETE,
        total_transactions=4,
        matched_count=0,
        exception_count=2,
        pending_review_count=2,
        total_value_reconciled=Decimal("0.0000"),
        created_by=user.id,
        started_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
    )
    db.add(run)

    tx_s1 = Transaction(
        id=uuid.uuid4(),
        organization_id=org.id,
        upload_id=u_stmt.id,
        reconciliation_run_id=run.id,
        source=TransactionSource.STATEMENT,
        transaction_date=datetime(2026, 8, 1, tzinfo=timezone.utc),
        description="Vendor SaaS Invoice 101",
        normalized_description="vendor saas invoice 101",
        amount=Decimal("500.0000"),
        currency="USD",
        status=TransactionStatus.PENDING_REVIEW,
        raw_data={},
    )
    tx_l1 = Transaction(
        id=uuid.uuid4(),
        organization_id=org.id,
        upload_id=u_ledg.id,
        reconciliation_run_id=run.id,
        source=TransactionSource.LEDGER,
        transaction_date=datetime(2026, 8, 3, tzinfo=timezone.utc),
        description="SaaS Vendor Monthly",
        normalized_description="saas vendor monthly",
        amount=Decimal("500.0000"),
        currency="USD",
        status=TransactionStatus.PENDING_REVIEW,
        raw_data={},
    )
    tx_s2 = Transaction(
        id=uuid.uuid4(),
        organization_id=org.id,
        upload_id=u_stmt.id,
        reconciliation_run_id=run.id,
        source=TransactionSource.STATEMENT,
        transaction_date=datetime(2026, 8, 1, tzinfo=timezone.utc),
        description="Unrelated High Value Transfer",
        amount=Decimal("8000.0000"),
        currency="USD",
        status=TransactionStatus.EXCEPTION,
        raw_data={},
    )
    db.add_all([tx_s1, tx_l1, tx_s2])
    await db.flush()

    exc1 = ReconciliationException(
        id=uuid.uuid4(),
        organization_id=org.id,
        reconciliation_run_id=run.id,
        transaction_id=tx_s1.id,
        best_candidate_transaction_id=tx_l1.id,
        reason_text="Review Required (Confidence 75.0%: Amount matches; 2-day date difference)",
        priority=ExceptionPriority.MEDIUM,
        status=ExceptionStatus.REVIEWING,
    )
    exc2 = ReconciliationException(
        id=uuid.uuid4(),
        organization_id=org.id,
        reconciliation_run_id=run.id,
        transaction_id=tx_s2.id,
        best_candidate_transaction_id=None,
        reason_text="Unmatched Statement: No counterparty found for USD 8000.00",
        priority=ExceptionPriority.HIGH,
        status=ExceptionStatus.OPEN,
    )
    db.add_all([exc1, exc2])
    await db.commit()

    token = create_access_token(user_id=user.id)
    return org, user, token, run, exc1, exc2, tx_s1, tx_l1, tx_s2


@pytest.mark.asyncio
async def test_list_exceptions_with_filters_and_pagination(
    async_client: AsyncClient, db_session: AsyncSession
):
    """Test GET /api/v1/exceptions with pagination, priority, and status filters."""
    org, user, token, run, exc1, exc2, tx_s1, tx_l1, tx_s2 = await setup_test_context(db_session)
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": str(org.id)}

    # 1. List all exceptions
    res = await async_client.get("/api/v1/exceptions", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2
    assert data["items"][0]["amount"] is not None
    assert data["items"][0]["transaction"] is not None

    # 2. Filter by status=reviewing
    res_filt = await async_client.get("/api/v1/exceptions?status=reviewing", headers=headers)
    assert res_filt.status_code == 200
    data_filt = res_filt.json()
    assert data_filt["total"] == 1
    assert data_filt["items"][0]["id"] == str(exc1.id)

    # 3. Filter by priority=high
    res_pri = await async_client.get("/api/v1/exceptions?priority=high", headers=headers)
    assert res_pri.status_code == 200
    data_pri = res_pri.json()
    assert data_pri["total"] == 1
    assert data_pri["items"][0]["id"] == str(exc2.id)

    # 4. Filter by run_id
    res_run = await async_client.get(f"/api/v1/exceptions?run_id={run.id}", headers=headers)
    assert res_run.status_code == 200
    assert res_run.json()["total"] == 2


@pytest.mark.asyncio
async def test_get_single_exception_review_drawer_detail(
    async_client: AsyncClient, db_session: AsyncSession
):
    """Test GET /api/v1/exceptions/{id} for review drawer payload."""
    org, user, token, run, exc1, exc2, tx_s1, tx_l1, tx_s2 = await setup_test_context(db_session)
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": str(org.id)}

    res = await async_client.get(f"/api/v1/exceptions/{exc1.id}", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == str(exc1.id)
    assert data["statement_transaction"]["id"] == str(tx_s1.id)
    assert data["candidate_transaction"]["id"] == str(tx_l1.id)
    assert "explanation_details" in data
    assert data["priority"] == "medium"


@pytest.mark.asyncio
async def test_manual_resolve_confirm_match(
    async_client: AsyncClient, db_session: AsyncSession
):
    """
    Test confirming a match on an exception:
    - Creates Match with method=manual
    - Updates transaction statuses to matched
    - Updates exception status to resolved
    - Updates run statistics (matched_count, total_value)
    - Records AuditLog
    """
    org, user, token, run, exc1, exc2, tx_s1, tx_l1, tx_s2 = await setup_test_context(db_session)
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": str(org.id)}

    res = await async_client.post(
        f"/api/v1/exceptions/{exc1.id}/resolve",
        headers=headers,
        json={"action": "confirm_match", "note": "Verified invoice match"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "resolved"
    assert "match_id" in data
    match_id = uuid.UUID(data["match_id"])

    # 1. Verify Match record
    m_stmt = select(Match).where(Match.id == match_id)
    m_res = await db_session.execute(m_stmt)
    match_rec = m_res.scalar_one_or_none()
    assert match_rec is not None
    assert match_rec.method == MatchMethod.MANUAL
    assert match_rec.confidence == Decimal("1.0000")
    assert match_rec.score_details["note"] == "Verified invoice match"

    # 2. Verify Transactions updated
    await db_session.refresh(tx_s1)
    await db_session.refresh(tx_l1)
    assert tx_s1.status == TransactionStatus.MATCHED
    assert tx_l1.status == TransactionStatus.MATCHED

    # 3. Verify Run Statistics updated
    await db_session.refresh(run)
    assert run.matched_count == 2
    assert run.pending_review_count == 1
    assert float(run.total_value_reconciled) == 500.00

    # 4. Verify Audit Log recorded
    audit_stmt = select(AuditLog).where(
        AuditLog.entity_id == exc1.id,
        AuditLog.action == "exception.resolved_match",
    )
    a_res = await db_session.execute(audit_stmt)
    assert a_res.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_manual_resolve_reject(
    async_client: AsyncClient, db_session: AsyncSession
):
    """Test rejecting an exception."""
    org, user, token, run, exc1, exc2, tx_s1, tx_l1, tx_s2 = await setup_test_context(db_session)
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": str(org.id)}

    res = await async_client.post(
        f"/api/v1/exceptions/{exc2.id}/resolve",
        headers=headers,
        json={"action": "reject", "note": "Fraudulent charge under investigation"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "rejected"

    await db_session.refresh(exc2)
    assert exc2.status == ExceptionStatus.REJECTED
    assert exc2.resolution_action == "reject"


@pytest.mark.asyncio
async def test_prevent_duplicate_resolution(
    async_client: AsyncClient, db_session: AsyncSession
):
    """Ensure resolving an already finalized exception returns HTTP 400."""
    org, user, token, run, exc1, exc2, tx_s1, tx_l1, tx_s2 = await setup_test_context(db_session)
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": str(org.id)}

    # Resolve once
    res1 = await async_client.post(
        f"/api/v1/exceptions/{exc1.id}/resolve",
        headers=headers,
        json={"action": "confirm_match"},
    )
    assert res1.status_code == 200

    # Attempt to resolve again
    res2 = await async_client.post(
        f"/api/v1/exceptions/{exc1.id}/resolve",
        headers=headers,
        json={"action": "reject"},
    )
    assert res2.status_code == 400
    assert "already finalized" in res2.json()["detail"]


@pytest.mark.asyncio
async def test_bulk_resolution_exceptions(
    async_client: AsyncClient, db_session: AsyncSession
):
    """Test resolving multiple exceptions in batch via POST /api/v1/exceptions/bulk-resolve."""
    org, user, token, run, exc1, exc2, tx_s1, tx_l1, tx_s2 = await setup_test_context(db_session)
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": str(org.id)}

    res = await async_client.post(
        "/api/v1/exceptions/bulk-resolve",
        headers=headers,
        json={
            "exception_ids": [str(exc1.id), str(exc2.id)],
            "action": "reject",
            "note": "Bulk rejected by analyst",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total_requested"] == 2
    assert data["resolved_count"] == 2
    assert data["failed_count"] == 0


@pytest.mark.asyncio
async def test_cross_tenant_exception_blocked(
    async_client: AsyncClient, db_session: AsyncSession
):
    """Ensure user from Tenant 1 cannot access or resolve Tenant 2's exception."""
    org1, user1, token1, _, exc1, _, _, _, _ = await setup_test_context(db_session, "Tenant 1")
    org2, user2, token2, _, exc2, _, _, _, _ = await setup_test_context(db_session, "Tenant 2")

    # User 1 tries to access User 2's exception with Tenant 1's header
    headers1 = {"Authorization": f"Bearer {token1}", "X-Organization-Id": str(org1.id)}
    res = await async_client.get(f"/api/v1/exceptions/{exc2.id}", headers=headers1)
    assert res.status_code == 404

    # User 1 tries to pass Org 2 header
    headers_spoof = {"Authorization": f"Bearer {token1}", "X-Organization-Id": str(org2.id)}
    res_spoof = await async_client.get(f"/api/v1/exceptions/{exc2.id}", headers=headers_spoof)
    assert res_spoof.status_code == 403
