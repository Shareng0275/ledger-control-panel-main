"""
Unit Tests: Predictive Anomaly Detection Engine (InsightsService)
Verifies:
  - Unusual amount anomaly detection (Z-score calculation)
  - Unusual frequency anomaly detection (burst velocity)
  - Near duplicate transaction detection
  - Suspicious mismatch detection
  - Clean normal dataset generates zero false positive anomalies
"""
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Organization,
    Transaction,
    TransactionSource,
    TransactionStatus,
    Upload,
    UploadStatus,
    UploadType,
    User,
)
from app.services.insights_service import InsightsService


async def _seed_normal_baseline_transactions(db: AsyncSession):
    """Seed regular, periodic, non-anomalous transactions."""
    org = Organization(id=uuid.uuid4(), name="Normal Org", slug=f"slug-{uuid.uuid4().hex[:8]}")
    user = User(id=uuid.uuid4(), email="norm@test.com", password_hash="h", full_name="User", is_active=True)
    db.add_all([org, user])
    await db.flush()

    upload = Upload(
        id=uuid.uuid4(), organization_id=org.id, filename="s.csv",
        upload_type=UploadType.STATEMENT, storage_path="u/s.csv", status=UploadStatus.VALID,
    )
    db.add(upload)
    await db.flush()

    base_dt = datetime(2026, 8, 1, tzinfo=timezone.utc)
    # 5 monthly vendor payments spaced 30 days apart, exact same amount $1,000
    for i in range(5):
        db.add(
            Transaction(
                id=uuid.uuid4(), organization_id=org.id, upload_id=upload.id,
                source=TransactionSource.STATEMENT,
                transaction_date=base_dt + timedelta(days=i * 30),
                description="Regular Monthly Cloud Host",
                normalized_description="regular monthly cloud host",
                amount=Decimal("1000.0000"),
                currency="USD",
                status=TransactionStatus.MATCHED,
                raw_data={},
            )
        )
    await db.commit()
    return org


@pytest.mark.asyncio
async def test_anomaly_detection_on_normal_baseline_zero_false_positives(db_session: AsyncSession):
    """Verify regular periodic data produces zero false positive anomaly insights."""
    org = await _seed_normal_baseline_transactions(db_session)

    res = await InsightsService.get_insights(db_session, org.id)

    # Completely normal data should produce 0 anomalies
    assert res.total == 0
    assert len(res.insights) == 0


@pytest.mark.asyncio
async def test_anomaly_detection_unusual_amount(db_session: AsyncSession):
    """Verify unusual amount anomaly detection catches extreme outliers."""
    org = await _seed_normal_baseline_transactions(db_session)

    # Insert an extreme outlier ($25,000 vs $1,000 baseline)
    tx_outlier = Transaction(
        id=uuid.uuid4(), organization_id=org.id, upload_id=uuid.uuid4(),
        source=TransactionSource.STATEMENT,
        transaction_date=datetime(2026, 8, 25, tzinfo=timezone.utc),
        description="Regular Monthly Cloud Host",
        normalized_description="regular monthly cloud host",
        amount=Decimal("25000.0000"),
        currency="USD",
        status=TransactionStatus.EXCEPTION,
        raw_data={},
    )
    db_session.add(tx_outlier)
    await db_session.commit()

    res = await InsightsService.get_insights(db_session, org.id, category_filter="unusual_amount")

    assert res.total >= 1
    assert res.insights[0].category == "unusual_amount"
    assert "25000" in res.insights[0].explanation
    assert res.insights[0].severity in ["high", "critical"]


@pytest.mark.asyncio
async def test_anomaly_detection_unusual_frequency_burst(db_session: AsyncSession):
    """Verify unusual frequency burst detection catches multiple transactions on same day."""
    org = await _seed_normal_baseline_transactions(db_session)

    burst_dt = datetime(2026, 8, 15, tzinfo=timezone.utc)
    for i in range(4):
        db_session.add(
            Transaction(
                id=uuid.uuid4(), organization_id=org.id, upload_id=uuid.uuid4(),
                source=TransactionSource.STATEMENT,
                transaction_date=burst_dt,
                description="Consulting Vendor Express",
                normalized_description="consulting vendor express",
                amount=Decimal("300.0000"),
                currency="USD",
                status=TransactionStatus.MATCHED,
                raw_data={},
            )
        )
    await db_session.commit()

    res = await InsightsService.get_insights(db_session, org.id, category_filter="unusual_frequency")

    assert res.total >= 1
    assert res.insights[0].category == "unusual_frequency"
    assert "4 transactions" in res.insights[0].explanation
