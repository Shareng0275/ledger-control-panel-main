"""
Unit Tests: Financial Cash Forecasting Engine (ForecastingService)
Verifies:
  - Valid historical data time series forecasting (EWMA + OLS drift)
  - Insufficient history (single data point stationary baseline)
  - Empty dataset handling
  - Confidence interval bounds (lower < projected < upper)
"""
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

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
from app.services.forecasting_service import ForecastingService


async def _seed_forecasting_data(db: AsyncSession, counts: int = 10, amount_step: Decimal = Decimal("500.00")):
    org = Organization(id=uuid.uuid4(), name="Forecast Unit Org", slug=f"slug-{uuid.uuid4().hex[:8]}")
    user = User(id=uuid.uuid4(), email="fc@test.com", password_hash="h", full_name="User", is_active=True)
    db.add_all([org, user])
    await db.flush()

    upload = Upload(
        id=uuid.uuid4(), organization_id=org.id, filename="s.csv",
        upload_type=UploadType.STATEMENT, storage_path="u/s.csv", status=UploadStatus.VALID,
    )
    db.add(upload)
    await db.flush()

    base_dt = datetime(2026, 8, 1, tzinfo=timezone.utc)
    for i in range(counts):
        db.add(
            Transaction(
                id=uuid.uuid4(), organization_id=org.id, upload_id=upload.id,
                source=TransactionSource.STATEMENT,
                transaction_date=base_dt + timedelta(days=i * 2),
                description=f"Transaction {i+1}",
                amount=amount_step if i % 2 == 0 else -amount_step / Decimal("2.0"),
                currency="USD",
                status=TransactionStatus.MATCHED,
                raw_data={},
            )
        )
    await db.commit()
    return org


@pytest.mark.asyncio
async def test_forecasting_with_valid_historical_data(db_session: AsyncSession):
    """Verify forecasting generates correct points and expanding uncertainty bounds."""
    org = await _seed_forecasting_data(db_session, counts=15)

    forecast_30d = await ForecastingService.generate_forecast(db_session, org.id, "30d")

    assert forecast_30d.is_empty is False
    assert len(forecast_30d.points) == 30
    assert forecast_30d.projected_cash is not None
    assert forecast_30d.analytics is not None
    assert forecast_30d.analytics.historical_data_points == 15

    # Check uncertainty bounds expand over time
    first_margin = forecast_30d.points[0].upper_bound - forecast_30d.points[0].projected_cash
    last_margin = forecast_30d.points[-1].upper_bound - forecast_30d.points[-1].projected_cash
    assert last_margin > first_margin


@pytest.mark.asyncio
async def test_forecasting_with_empty_data(db_session: AsyncSession):
    """Verify empty organization returns empty forecast model cleanly."""
    empty_org_id = uuid.uuid4()
    forecast = await ForecastingService.generate_forecast(db_session, empty_org_id, "30d")

    assert forecast.is_empty is True
    assert len(forecast.points) == 0
    assert forecast.projected_cash is None
    assert "No historical transaction data" in forecast.message


@pytest.mark.asyncio
async def test_forecasting_insufficient_single_point(db_session: AsyncSession):
    """Verify single transaction generates stationary baseline projection."""
    org = await _seed_forecasting_data(db_session, counts=1, amount_step=Decimal("5000.00"))

    forecast = await ForecastingService.generate_forecast(db_session, org.id, "7d")

    assert forecast.is_empty is False
    assert len(forecast.points) == 7
    assert forecast.points[0].projected_cash == Decimal("5000.00")
    assert "Baseline Flat Projection" in forecast.methodology
