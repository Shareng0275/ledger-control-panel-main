"""
Tests for Part 8: Dashboard KPIs + Transactions API
Covers:
  - Transaction listing with pagination, search, filters, sorting
  - Transaction detail with match info and audit history
  - Dashboard KPI summary with confidence distribution
  - Organization isolation
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from httpx import AsyncClient
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


async def _build_dashboard_context(db: AsyncSession, org_name: str = "Dashboard Org"):
    """Create org, user, uploads, run, transactions, matches, exceptions, and audit log."""
    org = Organization(id=uuid.uuid4(), name=org_name, slug=f"slug-{uuid.uuid4().hex[:8]}")
    user = User(
        id=uuid.uuid4(),
        email=f"user-{uuid.uuid4().hex[:8]}@test.com",
        password_hash="hash",
        full_name="Dashboard User",
        is_active=True,
    )
    db.add_all([org, user])
    await db.flush()

    m = Membership(id=uuid.uuid4(), organization_id=org.id, user_id=user.id, role=MembershipRole.ADMIN)
    db.add(m)

    u_stmt = Upload(
        id=uuid.uuid4(), organization_id=org.id, filename="stmt.csv",
        upload_type=UploadType.STATEMENT, storage_path="u/stmt.csv", status=UploadStatus.VALID,
    )
    u_ledg = Upload(
        id=uuid.uuid4(), organization_id=org.id, filename="ledg.csv",
        upload_type=UploadType.LEDGER, storage_path="u/ledg.csv", status=UploadStatus.VALID,
    )
    db.add_all([u_stmt, u_ledg])
    await db.flush()

    run = ReconciliationRun(
        id=uuid.uuid4(), organization_id=org.id,
        statement_upload_id=u_stmt.id, ledger_upload_id=u_ledg.id,
        status=ReconciliationStatus.COMPLETE,
        total_transactions=6, matched_count=2, exception_count=1, pending_review_count=1,
        total_value_reconciled=Decimal("3500.00"), average_confidence=Decimal("0.9200"),
        created_by=user.id,
        started_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        completed_at=datetime(2026, 8, 1, 0, 5, tzinfo=timezone.utc),
    )
    db.add(run)
    await db.flush()

    # ─── Matched pair (deterministic) ───────────────────────────────────────
    tx_s1 = Transaction(
        id=uuid.uuid4(), organization_id=org.id, upload_id=u_stmt.id,
        reconciliation_run_id=run.id, source=TransactionSource.STATEMENT,
        transaction_date=datetime(2026, 8, 1, tzinfo=timezone.utc),
        description="AWS Cloud Invoice #1001",
        normalized_description="aws cloud invoice #1001",
        amount=Decimal("1500.0000"), currency="USD",
        external_reference="REF-AWS-1001", normalized_reference="ref-aws-1001",
        status=TransactionStatus.MATCHED, confidence=Decimal("1.0000"),
        raw_data={"original": "row1"},
    )
    tx_l1 = Transaction(
        id=uuid.uuid4(), organization_id=org.id, upload_id=u_ledg.id,
        reconciliation_run_id=run.id, source=TransactionSource.LEDGER,
        transaction_date=datetime(2026, 8, 1, tzinfo=timezone.utc),
        description="AWS Cloud Payment",
        normalized_description="aws cloud payment",
        amount=Decimal("1500.0000"), currency="USD",
        external_reference="REF-AWS-1001", normalized_reference="ref-aws-1001",
        status=TransactionStatus.MATCHED, confidence=Decimal("1.0000"),
        raw_data={"original": "row2"},
    )

    # ─── Matched pair (fuzzy) ───────────────────────────────────────────────
    tx_s2 = Transaction(
        id=uuid.uuid4(), organization_id=org.id, upload_id=u_stmt.id,
        reconciliation_run_id=run.id, source=TransactionSource.STATEMENT,
        transaction_date=datetime(2026, 8, 5, tzinfo=timezone.utc),
        description="Office Supplies Order",
        normalized_description="office supplies order",
        amount=Decimal("2000.0000"), currency="USD",
        status=TransactionStatus.MATCHED, confidence=Decimal("0.9100"),
        raw_data={},
    )
    tx_l2 = Transaction(
        id=uuid.uuid4(), organization_id=org.id, upload_id=u_ledg.id,
        reconciliation_run_id=run.id, source=TransactionSource.LEDGER,
        transaction_date=datetime(2026, 8, 6, tzinfo=timezone.utc),
        description="Supplies Office Purchase",
        normalized_description="supplies office purchase",
        amount=Decimal("2000.0000"), currency="USD",
        status=TransactionStatus.MATCHED, confidence=Decimal("0.9100"),
        raw_data={},
    )

    # ─── Pending review ─────────────────────────────────────────────────────
    tx_s3 = Transaction(
        id=uuid.uuid4(), organization_id=org.id, upload_id=u_stmt.id,
        reconciliation_run_id=run.id, source=TransactionSource.STATEMENT,
        transaction_date=datetime(2026, 8, 10, tzinfo=timezone.utc),
        description="Consulting Fee Q3",
        amount=Decimal("750.0000"), currency="USD",
        status=TransactionStatus.PENDING_REVIEW, confidence=Decimal("0.7200"),
        raw_data={},
    )

    # ─── Exception ──────────────────────────────────────────────────────────
    tx_s4 = Transaction(
        id=uuid.uuid4(), organization_id=org.id, upload_id=u_stmt.id,
        reconciliation_run_id=run.id, source=TransactionSource.STATEMENT,
        transaction_date=datetime(2026, 8, 15, tzinfo=timezone.utc),
        description="Mystery Debit",
        amount=Decimal("5000.0000"), currency="USD",
        status=TransactionStatus.EXCEPTION,
        raw_data={},
    )

    db.add_all([tx_s1, tx_l1, tx_s2, tx_l2, tx_s3, tx_s4])
    await db.flush()

    # ─── Matches ────────────────────────────────────────────────────────────
    match1 = Match(
        id=uuid.uuid4(), organization_id=org.id, reconciliation_run_id=run.id,
        statement_transaction_id=tx_s1.id, ledger_transaction_id=tx_l1.id,
        method=MatchMethod.DETERMINISTIC, confidence=Decimal("1.0000"),
        score_details={"rule": "exact_reference"},
    )
    match2 = Match(
        id=uuid.uuid4(), organization_id=org.id, reconciliation_run_id=run.id,
        statement_transaction_id=tx_s2.id, ledger_transaction_id=tx_l2.id,
        method=MatchMethod.FUZZY, confidence=Decimal("0.9100"),
        score_details={"amount_score": 1.0, "date_score": 0.86, "description_score": 0.78},
    )
    db.add_all([match1, match2])

    # ─── Exception record ───────────────────────────────────────────────────
    exc1 = ReconciliationException(
        id=uuid.uuid4(), organization_id=org.id, reconciliation_run_id=run.id,
        transaction_id=tx_s4.id, best_candidate_transaction_id=None,
        reason_text="Unmatched: No counterparty found",
        priority=ExceptionPriority.HIGH, status=ExceptionStatus.OPEN,
    )
    db.add(exc1)

    # ─── Audit log entry ────────────────────────────────────────────────────
    audit = AuditLog(
        id=uuid.uuid4(), organization_id=org.id, actor_id=user.id,
        action="reconciliation.completed", entity_type="reconciliation_run",
        entity_id=run.id, details={"matched": 2},
    )
    # Also add an audit entry for tx_s1 (matched via deterministic)
    audit_tx = AuditLog(
        id=uuid.uuid4(), organization_id=org.id, actor_id=user.id,
        action="transaction.matched", entity_type="transaction",
        entity_id=tx_s1.id, details={"method": "deterministic", "confidence": "1.0000"},
    )
    db.add_all([audit, audit_tx])
    await db.commit()

    token = create_access_token(user_id=user.id)
    return {
        "org": org, "user": user, "token": token, "run": run,
        "tx_s1": tx_s1, "tx_l1": tx_l1, "tx_s2": tx_s2, "tx_l2": tx_l2,
        "tx_s3": tx_s3, "tx_s4": tx_s4,
        "match1": match1, "match2": match2, "exc1": exc1,
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  TRANSACTIONS API
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_transactions_list_pagination(async_client: AsyncClient, db_session: AsyncSession):
    """Verify paginated transaction listing returns correct structure and counts."""
    ctx = await _build_dashboard_context(db_session)
    headers = {"Authorization": f"Bearer {ctx['token']}", "X-Organization-Id": str(ctx["org"].id)}

    res = await async_client.get("/api/v1/transactions", headers=headers, params={"page": 1, "page_size": 3})
    assert res.status_code == 200
    data = res.json()

    assert data["total"] == 6
    assert len(data["items"]) == 3
    assert data["page"] == 1
    assert data["total_pages"] == 2
    assert data["has_next"] is True

    # Page 2
    res2 = await async_client.get("/api/v1/transactions", headers=headers, params={"page": 2, "page_size": 3})
    assert res2.status_code == 200
    data2 = res2.json()
    assert len(data2["items"]) == 3
    assert data2["has_prev"] is True
    assert data2["has_next"] is False


@pytest.mark.asyncio
async def test_transactions_search(async_client: AsyncClient, db_session: AsyncSession):
    """Verify safe text search against description and external_reference."""
    ctx = await _build_dashboard_context(db_session)
    headers = {"Authorization": f"Bearer {ctx['token']}", "X-Organization-Id": str(ctx["org"].id)}

    # Search by description keyword
    res = await async_client.get("/api/v1/transactions", headers=headers, params={"search": "AWS"})
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 2  # tx_s1 and tx_l1 both have "AWS"

    # Search by reference
    res2 = await async_client.get("/api/v1/transactions", headers=headers, params={"search": "REF-AWS-1001"})
    assert res2.status_code == 200
    assert res2.json()["total"] == 2


@pytest.mark.asyncio
async def test_transactions_status_and_source_filters(async_client: AsyncClient, db_session: AsyncSession):
    """Verify status and source filters work correctly."""
    ctx = await _build_dashboard_context(db_session)
    headers = {"Authorization": f"Bearer {ctx['token']}", "X-Organization-Id": str(ctx["org"].id)}

    # Filter by status
    res = await async_client.get("/api/v1/transactions", headers=headers, params={"status": "matched"})
    assert res.status_code == 200
    assert res.json()["total"] == 4  # tx_s1, tx_l1, tx_s2, tx_l2

    # Filter by source
    res2 = await async_client.get("/api/v1/transactions", headers=headers, params={"source": "statement"})
    assert res2.status_code == 200
    assert res2.json()["total"] == 4  # tx_s1, tx_s2, tx_s3, tx_s4

    # Combined filter
    res3 = await async_client.get(
        "/api/v1/transactions", headers=headers,
        params={"status": "exception", "source": "statement"},
    )
    assert res3.status_code == 200
    assert res3.json()["total"] == 1  # tx_s4 only


@pytest.mark.asyncio
async def test_transactions_date_range_filter(async_client: AsyncClient, db_session: AsyncSession):
    """Verify date range filtering."""
    ctx = await _build_dashboard_context(db_session)
    headers = {"Authorization": f"Bearer {ctx['token']}", "X-Organization-Id": str(ctx["org"].id)}

    res = await async_client.get(
        "/api/v1/transactions", headers=headers,
        params={"start_date": "2026-08-05T00:00:00Z", "end_date": "2026-08-10T23:59:59Z"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 3  # tx_s2 (Aug5), tx_l2 (Aug6), tx_s3 (Aug10)


@pytest.mark.asyncio
async def test_transactions_safe_sorting(async_client: AsyncClient, db_session: AsyncSession):
    """Verify whitelisted sorting works and rejects arbitrary field names."""
    ctx = await _build_dashboard_context(db_session)
    headers = {"Authorization": f"Bearer {ctx['token']}", "X-Organization-Id": str(ctx["org"].id)}

    # Sort by amount ascending
    res = await async_client.get(
        "/api/v1/transactions", headers=headers,
        params={"sort_by": "amount", "sort_order": "asc"},
    )
    assert res.status_code == 200
    items = res.json()["items"]
    amounts = [Decimal(str(item["amount"])) for item in items]
    assert amounts == sorted(amounts)

    # Sort by confidence descending
    res2 = await async_client.get(
        "/api/v1/transactions", headers=headers,
        params={"sort_by": "confidence", "sort_order": "desc"},
    )
    assert res2.status_code == 200

    # Unknown sort field should fall back to default (no error)
    res3 = await async_client.get(
        "/api/v1/transactions", headers=headers,
        params={"sort_by": "DROP TABLE transactions;--"},
    )
    assert res3.status_code == 200  # Falls back to transaction_date


@pytest.mark.asyncio
async def test_transactions_run_filter(async_client: AsyncClient, db_session: AsyncSession):
    """Verify filtering by reconciliation_run_id."""
    ctx = await _build_dashboard_context(db_session)
    headers = {"Authorization": f"Bearer {ctx['token']}", "X-Organization-Id": str(ctx["org"].id)}

    res = await async_client.get(
        "/api/v1/transactions", headers=headers,
        params={"run_id": str(ctx["run"].id)},
    )
    assert res.status_code == 200
    assert res.json()["total"] == 6

    # Non-existent run should return empty
    res2 = await async_client.get(
        "/api/v1/transactions", headers=headers,
        params={"run_id": str(uuid.uuid4())},
    )
    assert res2.status_code == 200
    assert res2.json()["total"] == 0


# ═══════════════════════════════════════════════════════════════════════════════
#  TRANSACTION DETAIL
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_transaction_detail_matched(async_client: AsyncClient, db_session: AsyncSession):
    """Verify GET /transactions/{id} returns match info with counterpart for a matched transaction."""
    ctx = await _build_dashboard_context(db_session)
    headers = {"Authorization": f"Bearer {ctx['token']}", "X-Organization-Id": str(ctx["org"].id)}

    res = await async_client.get(f"/api/v1/transactions/{ctx['tx_s1'].id}", headers=headers)
    assert res.status_code == 200
    data = res.json()

    # Core fields
    assert data["id"] == str(ctx["tx_s1"].id)
    assert data["description"] == "AWS Cloud Invoice #1001"
    assert Decimal(data["amount"]) == Decimal("1500.0000")
    assert data["source"] == "statement"
    assert data["status"] == "matched"
    assert data["external_reference"] == "REF-AWS-1001"
    assert data["currency"] == "USD"

    # Match info
    assert data["match_info"] is not None
    assert data["match_info"]["method"] == "deterministic"
    assert Decimal(data["match_info"]["confidence"]) == Decimal("1.0000")
    assert data["match_info"]["counterpart_transaction_id"] == str(ctx["tx_l1"].id)
    assert data["match_info"]["counterpart_description"] == "AWS Cloud Payment"
    assert Decimal(data["match_info"]["counterpart_amount"]) == Decimal("1500.0000")
    assert data["match_info"]["score_details"] is not None

    # Audit history
    assert len(data["audit_history"]) >= 1
    assert data["audit_history"][0]["action"] == "transaction.matched"


@pytest.mark.asyncio
async def test_transaction_detail_unmatched(async_client: AsyncClient, db_session: AsyncSession):
    """Verify unmatched transaction returns no match_info."""
    ctx = await _build_dashboard_context(db_session)
    headers = {"Authorization": f"Bearer {ctx['token']}", "X-Organization-Id": str(ctx["org"].id)}

    res = await async_client.get(f"/api/v1/transactions/{ctx['tx_s4'].id}", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "exception"
    assert data["match_info"] is None


@pytest.mark.asyncio
async def test_transaction_detail_not_found(async_client: AsyncClient, db_session: AsyncSession):
    """Verify 404 for non-existent transaction."""
    ctx = await _build_dashboard_context(db_session)
    headers = {"Authorization": f"Bearer {ctx['token']}", "X-Organization-Id": str(ctx["org"].id)}

    res = await async_client.get(f"/api/v1/transactions/{uuid.uuid4()}", headers=headers)
    assert res.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
#  DASHBOARD KPI SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_reconciliation_summary_kpis(async_client: AsyncClient, db_session: AsyncSession):
    """Verify GET /reconcile/{run_id}/summary returns correct KPIs."""
    ctx = await _build_dashboard_context(db_session)
    headers = {"Authorization": f"Bearer {ctx['token']}", "X-Organization-Id": str(ctx["org"].id)}

    res = await async_client.get(f"/api/v1/reconcile/{ctx['run'].id}/summary", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert data["run_id"] == str(ctx["run"].id)
    assert data["status"] == "complete"
    assert data["total_transactions"] == 6
    assert data["matched_count"] == 2
    assert data["exception_count"] == 1
    assert data["pending_review_count"] == 1
    assert Decimal(data["total_value_reconciled"]) == Decimal("3500.00")
    assert data["average_confidence"] is not None


@pytest.mark.asyncio
async def test_confidence_distribution(async_client: AsyncClient, db_session: AsyncSession):
    """Verify confidence distribution returns real data grouped by status."""
    ctx = await _build_dashboard_context(db_session)
    headers = {"Authorization": f"Bearer {ctx['token']}", "X-Organization-Id": str(ctx["org"].id)}

    res = await async_client.get(f"/api/v1/reconcile/{ctx['run'].id}/summary", headers=headers)
    assert res.status_code == 200
    data = res.json()

    dist = data["confidence_distribution"]
    assert isinstance(dist, list)
    assert len(dist) >= 2  # At least matched and one other status

    status_map = {d["status"]: d for d in dist}

    # Matched: 4 transactions (tx_s1, tx_l1, tx_s2, tx_l2)
    assert "matched" in status_map
    assert status_map["matched"]["count"] == 4
    assert Decimal(str(status_map["matched"]["total_amount"])) > 0
    assert status_map["matched"]["average_confidence"] is not None

    # Exception: 1 transaction (tx_s4)
    if "exception" in status_map:
        assert status_map["exception"]["count"] == 1


@pytest.mark.asyncio
async def test_match_method_breakdown(async_client: AsyncClient, db_session: AsyncSession):
    """Verify match method breakdown returns real counts."""
    ctx = await _build_dashboard_context(db_session)
    headers = {"Authorization": f"Bearer {ctx['token']}", "X-Organization-Id": str(ctx["org"].id)}

    res = await async_client.get(f"/api/v1/reconcile/{ctx['run'].id}/summary", headers=headers)
    assert res.status_code == 200
    data = res.json()

    breakdown = data["match_method_breakdown"]
    assert isinstance(breakdown, dict)
    assert breakdown.get("deterministic", 0) == 1
    assert breakdown.get("fuzzy", 0) == 1


@pytest.mark.asyncio
async def test_summary_not_found(async_client: AsyncClient, db_session: AsyncSession):
    """Verify 404 for non-existent run summary."""
    ctx = await _build_dashboard_context(db_session)
    headers = {"Authorization": f"Bearer {ctx['token']}", "X-Organization-Id": str(ctx["org"].id)}

    res = await async_client.get(f"/api/v1/reconcile/{uuid.uuid4()}/summary", headers=headers)
    assert res.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
#  ORGANIZATION ISOLATION
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_cross_tenant_transactions_blocked(async_client: AsyncClient, db_session: AsyncSession):
    """Ensure one tenant cannot see another tenant's transactions or summaries."""
    ctx1 = await _build_dashboard_context(db_session, "Tenant Alpha")
    ctx2 = await _build_dashboard_context(db_session, "Tenant Beta")

    h1 = {"Authorization": f"Bearer {ctx1['token']}", "X-Organization-Id": str(ctx1["org"].id)}
    h2 = {"Authorization": f"Bearer {ctx2['token']}", "X-Organization-Id": str(ctx2["org"].id)}

    # Tenant 1 sees only their own transactions
    res1 = await async_client.get("/api/v1/transactions", headers=h1)
    assert res1.status_code == 200
    ids_1 = {item["id"] for item in res1.json()["items"]}

    # Tenant 2 sees only their own transactions
    res2 = await async_client.get("/api/v1/transactions", headers=h2)
    assert res2.status_code == 200
    ids_2 = {item["id"] for item in res2.json()["items"]}

    # No overlap
    assert ids_1.isdisjoint(ids_2)

    # Tenant 1 cannot access Tenant 2's transaction detail
    t2_tx_id = ctx2["tx_s1"].id
    res_cross = await async_client.get(f"/api/v1/transactions/{t2_tx_id}", headers=h1)
    assert res_cross.status_code == 404

    # Tenant 1 cannot access Tenant 2's summary
    res_cross_sum = await async_client.get(f"/api/v1/reconcile/{ctx2['run'].id}/summary", headers=h1)
    assert res_cross_sum.status_code == 404

    # Spoofed org header should be denied
    h_spoof = {"Authorization": f"Bearer {ctx1['token']}", "X-Organization-Id": str(ctx2["org"].id)}
    res_spoof = await async_client.get("/api/v1/transactions", headers=h_spoof)
    assert res_spoof.status_code == 403
