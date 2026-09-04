"""
Tests for Part 9: Cash Forecasting + Financial Analytics
Verifies:
  - 7-day, 30-day, and 90-day forecasts
  - Real transaction data usage
  - Expanding confidence uncertainty bands
  - Empty history handling
  - Insufficient history handling (single point)
  - Invalid horizon validation
  - Cross-tenant organization isolation
"""
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models import (
    Membership,
    MembershipRole,
    Organization,
    Transaction,
    TransactionSource,
    TransactionStatus,
    Upload,
    UploadStatus,
    UploadType,
    User,
)


async def _create_tenant_with_transactions(
    db: AsyncSession,
    org_name: str = "Forecast Org",
    num_days: int = 15,
    daily_amount: Decimal = Decimal("1000.00"),
):
    """Helper to set up an organization with daily transactions over a specified date range."""
    org = Organization(id=uuid.uuid4(), name=org_name, slug=f"slug-{uuid.uuid4().hex[:8]}")
    user = User(
        id=uuid.uuid4(),
        email=f"cfo-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hash",
        full_name="CFO User",
        is_active=True,
    )
    db.add_all([org, user])
    await db.flush()

    m = Membership(id=uuid.uuid4(), organization_id=org.id, user_id=user.id, role=MembershipRole.ADMIN)
    db.add(m)

    upload = Upload(
        id=uuid.uuid4(),
        organization_id=org.id,
        filename="bank_stmt.csv",
        upload_type=UploadType.STATEMENT,
        storage_path="uploads/stmt.csv",
        status=UploadStatus.VALID,
    )
    db.add(upload)
    await db.flush()

    base_date = datetime(2026, 8, 1, tzinfo=timezone.utc)
    txs = []
    for i in range(num_days):
        t_date = base_date + timedelta(days=i)
        # Alternate between regular inflows and occasional expenses
        amount = daily_amount if (i + 1) % 3 != 0 else -daily_amount / Decimal("2.0")
        txs.append(
            Transaction(
                id=uuid.uuid4(),
                organization_id=org.id,
                upload_id=upload.id,
                source=TransactionSource.STATEMENT,
                transaction_date=t_date,
                description=f"Transaction Day {i+1}",
                amount=amount,
                currency="USD",
                status=TransactionStatus.MATCHED,
                raw_data={"day": i + 1},
            )
        )
    if txs:
        db.add_all(txs)
    await db.commit()

    token = create_access_token(user_id=user.id)
    return org, user, token


# ═══════════════════════════════════════════════════════════════════════════════
#  FORECAST HORIZONS & CONFIDENCE BANDS
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_7d_forecast_generation(async_client: AsyncClient, db_session: AsyncSession):
    """Verify 7-day forecast returns 7 points with correct bounds and structure."""
    org, user, token = await _create_tenant_with_transactions(db_session, "7D Org", num_days=10)
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": str(org.id)}

    res = await async_client.get("/api/v1/forecast?horizon=7d", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert data["horizon"] == "7d"
    assert data["currency"] == "USD"
    assert data["is_empty"] is False
    assert len(data["points"]) == 7
    assert data["projected_cash"] is not None
    assert data["confidence"] is not None

    # Check that points have proper fields and expanding bounds
    for i, pt in enumerate(data["points"]):
        assert "date" in pt
        assert Decimal(str(pt["lower_bound"])) <= Decimal(str(pt["projected_cash"])) <= Decimal(str(pt["upper_bound"]))
        # Frontend compatibility fields
        assert pt["cash"] is not None
        assert pt["lower"] is not None
        assert pt["upper"] is not None

    # Analytics
    assert data["analytics"] is not None
    assert data["analytics"]["trend_direction"] in ["positive", "negative", "neutral"]
    assert data["analytics"]["historical_data_points"] == 10


@pytest.mark.asyncio
async def test_30d_forecast_generation(async_client: AsyncClient, db_session: AsyncSession):
    """Verify 30-day forecast returns 30 points."""
    org, user, token = await _create_tenant_with_transactions(db_session, "30D Org", num_days=20)
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": str(org.id)}

    res = await async_client.get("/api/v1/forecast?horizon=30d", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert data["horizon"] == "30d"
    assert len(data["points"]) == 30
    assert data["analytics"]["historical_days_analyzed"] == 20


@pytest.mark.asyncio
async def test_90d_forecast_generation(async_client: AsyncClient, db_session: AsyncSession):
    """Verify 90-day forecast returns 90 points."""
    org, user, token = await _create_tenant_with_transactions(db_session, "90D Org", num_days=30)
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": str(org.id)}

    res = await async_client.get("/api/v1/forecast?horizon=90d", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert data["horizon"] == "90d"
    assert len(data["points"]) == 90

    # Verify confidence decay over longer horizons
    first_pt_conf = Decimal(str(data["points"][0]["confidence"]))
    last_pt_conf = Decimal(str(data["points"][-1]["confidence"]))
    assert first_pt_conf >= last_pt_conf


# ═══════════════════════════════════════════════════════════════════════════════
#  EDGE CASES & VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_empty_organization_forecast(async_client: AsyncClient, db_session: AsyncSession):
    """Verify empty organization returns an informative empty state without errors."""
    org, user, token = await _create_tenant_with_transactions(db_session, "Empty Org", num_days=0)
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": str(org.id)}

    res = await async_client.get("/api/v1/forecast?horizon=30d", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert data["is_empty"] is True
    assert len(data["points"]) == 0
    assert data["projected_cash"] is None
    assert "No historical transaction data found" in data["message"]


@pytest.mark.asyncio
async def test_insufficient_history_single_transaction(async_client: AsyncClient, db_session: AsyncSession):
    """Verify single transaction generates a stationary baseline forecast."""
    org, user, token = await _create_tenant_with_transactions(db_session, "Single Tx Org", num_days=1, daily_amount=Decimal("5000.00"))
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": str(org.id)}

    res = await async_client.get("/api/v1/forecast?horizon=7d", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert data["is_empty"] is False
    assert len(data["points"]) == 7
    assert Decimal(str(data["points"][0]["projected_cash"])) == Decimal("5000.00")
    assert "Baseline Flat Projection" in data["methodology"]


@pytest.mark.asyncio
async def test_invalid_horizon_rejected(async_client: AsyncClient, db_session: AsyncSession):
    """Verify invalid horizon query parameter triggers validation error."""
    org, user, token = await _create_tenant_with_transactions(db_session, "Validation Org", num_days=5)
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": str(org.id)}

    res = await async_client.get("/api/v1/forecast?horizon=365d", headers=headers)
    assert res.status_code == 422

    res_sql = await async_client.get("/api/v1/forecast?horizon=' OR 1=1--", headers=headers)
    assert res_sql.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════════
#  ORGANIZATION ISOLATION
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_cross_tenant_forecast_isolation(async_client: AsyncClient, db_session: AsyncSession):
    """Ensure Tenant 1's cash forecast is completely isolated from Tenant 2's data."""
    org1, user1, token1 = await _create_tenant_with_transactions(
        db_session, "Tenant 1", num_days=10, daily_amount=Decimal("1000.00")
    )
    org2, user2, token2 = await _create_tenant_with_transactions(
        db_session, "Tenant 2", num_days=10, daily_amount=Decimal("50000.00")
    )

    h1 = {"Authorization": f"Bearer {token1}", "X-Organization-Id": str(org1.id)}
    h2 = {"Authorization": f"Bearer {token2}", "X-Organization-Id": str(org2.id)}

    res1 = await async_client.get("/api/v1/forecast?horizon=7d", headers=h1)
    res2 = await async_client.get("/api/v1/forecast?horizon=7d", headers=h2)

    assert res1.status_code == 200
    assert res2.status_code == 200

    data1 = res1.json()
    data2 = res2.json()

    # Balances must reflect their own respective amounts
    assert Decimal(str(data1["analytics"]["current_cash_balance"])) < Decimal(str(data2["analytics"]["current_cash_balance"]))

    # Spoofed organization header must be rejected
    h_spoofed = {"Authorization": f"Bearer {token1}", "X-Organization-Id": str(org2.id)}
    res_spoof = await async_client.get("/api/v1/forecast?horizon=7d", headers=h_spoofed)
    assert res_spoof.status_code == 403
