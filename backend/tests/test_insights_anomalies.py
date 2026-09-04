"""
Tests for Part 11: AI Insights + Predictive Anomaly Detection
Verifies:
  - Unusual amount anomaly detection
  - Unusual frequency anomaly detection
  - Near duplicate transaction detection
  - Suspicious mismatch detection
  - High-risk exception anomaly detection
  - Severity and category filtering
  - Reconciliation run filtering
  - Organization isolation
  - Evidence-based explainability
"""
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models import (
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


async def _setup_insights_dataset(db: AsyncSession, org_name: str = "Anomaly Org"):
    """
    Sets up a realistic dataset with all 5 distinct anomaly types:
    1. Unusual Amount: AWS invoice of $15,000 when historical average is $1,000
    2. Unusual Frequency: 4 payments to SaaS Vendor within 24 hours
    3. Near Duplicate: Two $850 payments to 'Consulting Partner' 1 day apart
    4. Suspicious Mismatch: Match with $200 amount discrepancy
    5. High-Risk Exception: $25,000 unresolved wire transfer exception
    """
    org = Organization(id=uuid.uuid4(), name=org_name, slug=f"slug-{uuid.uuid4().hex[:8]}")
    user = User(
        id=uuid.uuid4(),
        email=f"auditor-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hash",
        full_name="Risk Auditor",
        is_active=True,
    )
    db.add_all([org, user])
    await db.flush()

    m = Membership(id=uuid.uuid4(), organization_id=org.id, user_id=user.id, role=MembershipRole.ANALYST)
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
        total_transactions=15, matched_count=10, exception_count=5, pending_review_count=0,
        total_value_reconciled=Decimal("45000.00"), average_confidence=Decimal("0.9400"),
        created_by=user.id,
        started_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
    )
    db.add(run)
    await db.flush()

    base_date = datetime(2026, 8, 1, tzinfo=timezone.utc)
    txs = []

    # 1. Unusual Amount: Baseline historical AWS transactions of ~$1,000, plus one extreme $15,000 outlier
    for i in range(4):
        txs.append(
            Transaction(
                id=uuid.uuid4(), organization_id=org.id, upload_id=u_stmt.id,
                reconciliation_run_id=run.id, source=TransactionSource.STATEMENT,
                transaction_date=base_date + timedelta(days=i * 5),
                description="AWS Cloud Infrastructure",
                normalized_description="aws cloud infrastructure",
                amount=Decimal(f"{1000 + i * 50}.0000"), currency="USD",
                status=TransactionStatus.MATCHED, raw_data={},
            )
        )
    # The extreme outlier for AWS
    tx_unusual_amt = Transaction(
        id=uuid.uuid4(), organization_id=org.id, upload_id=u_stmt.id,
        reconciliation_run_id=run.id, source=TransactionSource.STATEMENT,
        transaction_date=base_date + timedelta(days=25),
        description="AWS Cloud Infrastructure",
        normalized_description="aws cloud infrastructure",
        amount=Decimal("15000.0000"), currency="USD",
        status=TransactionStatus.EXCEPTION, raw_data={},
    )
    txs.append(tx_unusual_amt)

    # 2. Unusual Frequency: 4 transactions on the same day for "SaaS Subscription"
    for i in range(4):
        txs.append(
            Transaction(
                id=uuid.uuid4(), organization_id=org.id, upload_id=u_stmt.id,
                reconciliation_run_id=run.id, source=TransactionSource.STATEMENT,
                transaction_date=base_date + timedelta(days=10),
                description="SaaS Subscription Platform",
                normalized_description="saas subscription platform",
                amount=Decimal(f"{250 + i * 10}.0000"), currency="USD",
                status=TransactionStatus.MATCHED, raw_data={},
            )
        )

    # 3. Near Duplicate: Two $850 transactions 1 day apart with slightly varied descriptions
    tx_dup1 = Transaction(
        id=uuid.uuid4(), organization_id=org.id, upload_id=u_stmt.id,
        reconciliation_run_id=run.id, source=TransactionSource.STATEMENT,
        transaction_date=base_date + timedelta(days=15),
        description="Consulting Services Invoice 101",
        normalized_description="consulting services invoice 101",
        amount=Decimal("850.0000"), currency="USD",
        status=TransactionStatus.MATCHED, raw_data={},
    )
    tx_dup2 = Transaction(
        id=uuid.uuid4(), organization_id=org.id, upload_id=u_stmt.id,
        reconciliation_run_id=run.id, source=TransactionSource.STATEMENT,
        transaction_date=base_date + timedelta(days=16),
        description="Consulting Services Invoice 102",
        normalized_description="consulting services invoice 102",
        amount=Decimal("850.0000"), currency="USD",
        status=TransactionStatus.MATCHED, raw_data={},
    )
    txs.extend([tx_dup1, tx_dup2])

    # 4. Suspicious Mismatch: Statement tx ($5,000) vs Ledger tx ($4,800) matched with discrepancy
    tx_s_var = Transaction(
        id=uuid.uuid4(), organization_id=org.id, upload_id=u_stmt.id,
        reconciliation_run_id=run.id, source=TransactionSource.STATEMENT,
        transaction_date=base_date + timedelta(days=18),
        description="Hardware Equipment Purchase",
        amount=Decimal("5000.0000"), currency="USD",
        status=TransactionStatus.MATCHED, raw_data={},
    )
    tx_l_var = Transaction(
        id=uuid.uuid4(), organization_id=org.id, upload_id=u_ledg.id,
        reconciliation_run_id=run.id, source=TransactionSource.LEDGER,
        transaction_date=base_date + timedelta(days=18),
        description="Hardware Equipment Purchase",
        amount=Decimal("4800.0000"), currency="USD",
        status=TransactionStatus.MATCHED, raw_data={},
    )
    txs.extend([tx_s_var, tx_l_var])

    # 5. High-Risk Exception: $25,000 unresolved wire transfer
    tx_high_risk = Transaction(
        id=uuid.uuid4(), organization_id=org.id, upload_id=u_stmt.id,
        reconciliation_run_id=run.id, source=TransactionSource.STATEMENT,
        transaction_date=base_date + timedelta(days=20),
        description="International Wire Transfer Outflow",
        amount=Decimal("25000.0000"), currency="USD",
        status=TransactionStatus.EXCEPTION, raw_data={},
    )
    txs.append(tx_high_risk)

    db.add_all(txs)
    await db.flush()

    # Create the Match with $200 variance
    match_var = Match(
        id=uuid.uuid4(), organization_id=org.id, reconciliation_run_id=run.id,
        statement_transaction_id=tx_s_var.id, ledger_transaction_id=tx_l_var.id,
        method=MatchMethod.FUZZY, confidence=Decimal("0.8900"),
        score_details={"variance": 200.0},
    )
    db.add(match_var)

    # Create High-Risk Exception
    exc_high_risk = ReconciliationException(
        id=uuid.uuid4(), organization_id=org.id, reconciliation_run_id=run.id,
        transaction_id=tx_high_risk.id, best_candidate_transaction_id=None,
        reason_text="Unmatched Wire: Material exposure with no ledger counterparty",
        priority=ExceptionPriority.HIGH, status=ExceptionStatus.OPEN,
    )
    db.add(exc_high_risk)
    await db.commit()

    token = create_access_token(user_id=user.id)
    return {
        "org": org, "user": user, "token": token, "run": run,
        "tx_unusual_amt": tx_unusual_amt, "tx_dup1": tx_dup1, "tx_dup2": tx_dup2,
        "tx_high_risk": tx_high_risk, "exc_high_risk": exc_high_risk,
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  ANOMALY DETECTION TESTS
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_get_all_insights_structure(async_client: AsyncClient, db_session: AsyncSession):
    """Verify GET /api/v1/insights returns detected anomalies with proper metadata and counts."""
    ctx = await _setup_insights_dataset(db_session)
    headers = {"Authorization": f"Bearer {ctx['token']}", "X-Organization-Id": str(ctx["org"].id)}

    res = await async_client.get("/api/v1/insights", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert "insights" in data
    assert data["total"] >= 4
    assert "severity_counts" in data
    assert "category_counts" in data

    categories = [i["category"] for i in data["insights"]]
    assert "unusual_amount" in categories
    assert "unusual_frequency" in categories
    assert "near_duplicate" in categories
    assert "suspicious_mismatch" in categories
    assert "high_risk_exception" in categories


@pytest.mark.asyncio
async def test_unusual_amount_anomaly(async_client: AsyncClient, db_session: AsyncSession):
    """Verify unusual amount anomaly is detected with statistical Z-score explanation."""
    ctx = await _setup_insights_dataset(db_session)
    headers = {"Authorization": f"Bearer {ctx['token']}", "X-Organization-Id": str(ctx["org"].id)}

    res = await async_client.get("/api/v1/insights?category=unusual_amount", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert data["total"] >= 1
    amt_insight = data["insights"][0]
    assert amt_insight["category"] == "unusual_amount"
    assert "15000" in amt_insight["explanation"]
    assert "standard deviations" in amt_insight["explanation"]
    assert amt_insight["severity"] in ["high", "critical"]
    assert amt_insight["score_details"] is not None


@pytest.mark.asyncio
async def test_unusual_frequency_anomaly(async_client: AsyncClient, db_session: AsyncSession):
    """Verify unusual frequency anomaly is detected for burst transactions."""
    ctx = await _setup_insights_dataset(db_session)
    headers = {"Authorization": f"Bearer {ctx['token']}", "X-Organization-Id": str(ctx["org"].id)}

    res = await async_client.get("/api/v1/insights?category=unusual_frequency", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert data["total"] >= 1
    freq_insight = data["insights"][0]
    assert freq_insight["category"] == "unusual_frequency"
    assert "4 transactions" in freq_insight["explanation"]
    assert "SaaS Subscription" in freq_insight["explanation"]


@pytest.mark.asyncio
async def test_near_duplicate_anomaly(async_client: AsyncClient, db_session: AsyncSession):
    """Verify near duplicate transactions with identical amounts are detected."""
    ctx = await _setup_insights_dataset(db_session)
    headers = {"Authorization": f"Bearer {ctx['token']}", "X-Organization-Id": str(ctx["org"].id)}

    res = await async_client.get("/api/v1/insights?category=near_duplicate", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert data["total"] >= 1
    dup_insight = data["insights"][0]
    assert dup_insight["category"] == "near_duplicate"
    assert "850.00" in dup_insight["explanation"]
    assert "similarity" in dup_insight["explanation"]


@pytest.mark.asyncio
async def test_suspicious_mismatch_anomaly(async_client: AsyncClient, db_session: AsyncSession):
    """Verify suspicious mismatch is detected for match with amount variance."""
    ctx = await _setup_insights_dataset(db_session)
    headers = {"Authorization": f"Bearer {ctx['token']}", "X-Organization-Id": str(ctx["org"].id)}

    res = await async_client.get("/api/v1/insights?category=suspicious_mismatch", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert data["total"] >= 1
    mismatch_insight = data["insights"][0]
    assert "200.00" in mismatch_insight["explanation"] or "Hardware" in mismatch_insight["explanation"]


@pytest.mark.asyncio
async def test_high_risk_exception_anomaly(async_client: AsyncClient, db_session: AsyncSession):
    """Verify high risk exceptions with large amounts are flagged with critical/high severity."""
    ctx = await _setup_insights_dataset(db_session)
    headers = {"Authorization": f"Bearer {ctx['token']}", "X-Organization-Id": str(ctx["org"].id)}

    res = await async_client.get("/api/v1/insights?category=high_risk_exception", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert data["total"] >= 1
    hr_insight = data["insights"][0]
    assert "25000" in hr_insight["explanation"]
    assert hr_insight["severity"] == "critical"


@pytest.mark.asyncio
async def test_severity_filter(async_client: AsyncClient, db_session: AsyncSession):
    """Verify filtering by severity returns only insights matching the severity."""
    ctx = await _setup_insights_dataset(db_session)
    headers = {"Authorization": f"Bearer {ctx['token']}", "X-Organization-Id": str(ctx["org"].id)}

    res = await async_client.get("/api/v1/insights?severity=critical", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert all(i["severity"] == "critical" for i in data["insights"])


@pytest.mark.asyncio
async def test_reconciliation_run_filter(async_client: AsyncClient, db_session: AsyncSession):
    """Verify filtering by reconciliation run ID scopes insights correctly."""
    ctx = await _setup_insights_dataset(db_session)
    headers = {"Authorization": f"Bearer {ctx['token']}", "X-Organization-Id": str(ctx["org"].id)}

    res = await async_client.get(f"/api/v1/insights?run_id={ctx['run'].id}", headers=headers)
    assert res.status_code == 200
    assert res.json()["total"] >= 1

    # Non-existent run ID should return 0
    res_fake = await async_client.get(f"/api/v1/insights?run_id={uuid.uuid4()}", headers=headers)
    assert res_fake.status_code == 200
    assert res_fake.json()["total"] == 0


@pytest.mark.asyncio
async def test_cross_tenant_insights_isolation(async_client: AsyncClient, db_session: AsyncSession):
    """Ensure Tenant 1 cannot access or see Tenant 2's insights."""
    ctx1 = await _setup_insights_dataset(db_session, "Tenant 1")
    ctx2 = await _setup_insights_dataset(db_session, "Tenant 2")

    h1 = {"Authorization": f"Bearer {ctx1['token']}", "X-Organization-Id": str(ctx1["org"].id)}
    h2 = {"Authorization": f"Bearer {ctx2['token']}", "X-Organization-Id": str(ctx2["org"].id)}

    res1 = await async_client.get("/api/v1/insights", headers=h1)
    res2 = await async_client.get("/api/v1/insights", headers=h2)

    assert res1.status_code == 200
    assert res2.status_code == 200

    # Ensure transaction IDs in Tenant 1's insights do NOT overlap with Tenant 2's transactions
    t1_tx_ids = {i["related_transaction_id"] for i in res1.json()["insights"] if i.get("related_transaction_id")}
    assert str(ctx2["tx_unusual_amt"].id) not in t1_tx_ids
    assert str(ctx2["tx_high_risk"].id) not in t1_tx_ids

    # Spoofed org header must be rejected
    h_spoofed = {"Authorization": f"Bearer {ctx1['token']}", "X-Organization-Id": str(ctx2["org"].id)}
    res_spoof = await async_client.get("/api/v1/insights", headers=h_spoofed)
    assert res_spoof.status_code == 403


@pytest.mark.asyncio
async def test_empty_organization_insights(async_client: AsyncClient, db_session: AsyncSession):
    """Verify empty organization returns empty insights list with no errors."""
    org = Organization(id=uuid.uuid4(), name="Empty Org", slug="empty-insights-slug")
    user = User(
        id=uuid.uuid4(), email="empty.ins@test.com", password_hash="hash", full_name="Empty User", is_active=True
    )
    db_session.add_all([org, user])
    await db_session.flush()

    m = Membership(id=uuid.uuid4(), organization_id=org.id, user_id=user.id, role=MembershipRole.ANALYST)
    db_session.add(m)
    await db_session.commit()

    token = create_access_token(user_id=user.id)
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": str(org.id)}

    res = await async_client.get("/api/v1/insights", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 0
    assert len(data["insights"]) == 0
