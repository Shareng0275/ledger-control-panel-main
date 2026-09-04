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
from app.services.fuzzy_matcher import FuzzyMatcher


async def setup_org_and_user(db_session: AsyncSession, name: str = "Fuzzy Org") -> tuple[Organization, User, str]:
    org = Organization(id=uuid.uuid4(), name=name, slug=f"slug-{uuid.uuid4().hex[:8]}")
    user = User(
        id=uuid.uuid4(),
        email=f"fuzzy-{uuid.uuid4().hex[:8]}@acme.com",
        password_hash="hash",
        full_name="Fuzzy User",
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


def test_fuzzy_scorer_explainability_and_breakdown():
    """Unit test individual score components and human-readable explanation generation."""
    t_stmt = Transaction(
        id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        upload_id=uuid.uuid4(),
        source=TransactionSource.STATEMENT,
        transaction_date=datetime(2026, 8, 1, tzinfo=timezone.utc),
        description="Stripe Payout Ref 1001",
        normalized_description="stripe payout ref 1001",
        amount=Decimal("1500.0000"),
        currency="USD",
        external_reference="STMT-1001",
        normalized_reference="STMT1001",
        status=TransactionStatus.PENDING_REVIEW,
        raw_data={},
    )
    t_ledg = Transaction(
        id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        upload_id=uuid.uuid4(),
        source=TransactionSource.LEDGER,
        transaction_date=datetime(2026, 8, 2, tzinfo=timezone.utc),  # 1 day difference
        description="Stripe Inc Payouts",
        normalized_description="stripe inc payouts",
        amount=Decimal("1500.0000"),  # Exact amount
        currency="USD",
        external_reference="LEDG-1001",
        normalized_reference="LEDG1001",
        status=TransactionStatus.PENDING_REVIEW,
        raw_data={},
    )

    breakdown = FuzzyMatcher.score_pair(t_stmt, t_ledg)
    assert breakdown.amount_score == Decimal("1.0000")
    assert breakdown.date_score == Decimal("0.9500")
    assert breakdown.description_score > Decimal("0.7000")
    assert breakdown.overall_confidence >= Decimal("0.8500")
    assert "Amount matches exactly" in breakdown.explanation
    assert "Date differs by 1 day" in breakdown.explanation
    assert "Description similarity" in breakdown.explanation

    # Check to_dict JSONB serialization
    data = breakdown.to_dict()
    assert "overall_confidence" in data
    assert "explanation" in data


@pytest.mark.asyncio
async def test_fuzzy_high_confidence_auto_match(async_client: AsyncClient, db_session: AsyncSession):
    """
    Test that high-confidence candidate pair (>= 0.88) is auto-matched with MatchMethod.FUZZY
    and score details stored.
    """
    org, user, token = await setup_org_and_user(db_session, "Auto Match Org")
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": str(org.id)}

    stmt_csv = (
        "Date,Description,Amount,Reference\n"
        "2026-08-01,Amazon Web Services Cloud Hosting,1250.00,AWS-1001\n"
    )
    ledg_csv = (
        "Date,Description,Amount,Reference\n"
        "2026-08-01,AWS Cloud Hosting Monthly,1248.50,AWS-1001\n"  # Slight processing fee variance ($1.50) + same reference
    )

    res_s = await async_client.post("/api/v1/uploads/statement", headers=headers, files={"file": ("s.csv", io.BytesIO(stmt_csv.encode("utf-8")), "text/csv")})
    res_l = await async_client.post("/api/v1/uploads/ledger", headers=headers, files={"file": ("l.csv", io.BytesIO(ledg_csv.encode("utf-8")), "text/csv")})

    res_run = await async_client.post(
        "/api/v1/reconcile/run",
        headers=headers,
        json={"statement_upload_id": res_s.json()["upload_id"], "ledger_upload_id": res_l.json()["upload_id"]},
    )
    run_id = uuid.UUID(res_run.json()["run_id"])

    res_poll = await async_client.get(f"/api/v1/reconcile/{run_id}", headers=headers)
    data = res_poll.json()
    assert data["status"] == "complete"
    assert data["matched_count"] == 2  # 1 pair = 2 transactions matched
    assert data["exception_count"] == 0

    # Verify Match record
    m_stmt = select(Match).where(Match.reconciliation_run_id == run_id)
    m_res = await db_session.execute(m_stmt)
    matches = list(m_res.scalars().all())
    assert len(matches) == 1
    match = matches[0]
    assert match.method == MatchMethod.FUZZY
    assert match.confidence >= Decimal("0.8800")
    assert "amount_score" in match.score_details
    assert "explanation" in match.score_details


@pytest.mark.asyncio
async def test_fuzzy_medium_confidence_pending_review(async_client: AsyncClient, db_session: AsyncSession):
    """
    Test that medium-confidence pair (0.65 <= c < 0.88) is triaged to PENDING_REVIEW
    with status=REVIEWING and best candidate attached.
    """
    org, user, token = await setup_org_and_user(db_session, "Review Org")
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": str(org.id)}

    # 4-day date difference + partial description similarity
    stmt_csv = "Date,Description,Amount\n2026-08-01,Hubspot CRM Marketing,750.00\n"
    ledg_csv = "Date,Description,Amount\n2026-08-05,Marketing Tools Subscription,750.00\n"

    res_s = await async_client.post("/api/v1/uploads/statement", headers=headers, files={"file": ("s.csv", io.BytesIO(stmt_csv.encode("utf-8")), "text/csv")})
    res_l = await async_client.post("/api/v1/uploads/ledger", headers=headers, files={"file": ("l.csv", io.BytesIO(ledg_csv.encode("utf-8")), "text/csv")})

    res_run = await async_client.post(
        "/api/v1/reconcile/run",
        headers=headers,
        json={"statement_upload_id": res_s.json()["upload_id"], "ledger_upload_id": res_l.json()["upload_id"]},
    )
    run_id = uuid.UUID(res_run.json()["run_id"])

    res_poll = await async_client.get(f"/api/v1/reconcile/{run_id}", headers=headers)
    data = res_poll.json()
    assert data["status"] == "complete"
    assert data["matched_count"] == 0
    assert data["pending_review_count"] == 2  # Both statement and ledger in pending review

    # Verify ReconciliationException has status REVIEWING and candidate linked
    e_stmt = select(ReconciliationException).where(ReconciliationException.reconciliation_run_id == run_id)
    e_res = await db_session.execute(e_stmt)
    exceptions = list(e_res.scalars().all())
    assert len(exceptions) == 2
    assert all(e.status == ExceptionStatus.REVIEWING for e in exceptions)
    assert all(e.best_candidate_transaction_id is not None for e in exceptions)
    assert any("Review Required" in e.reason_text for e in exceptions)


@pytest.mark.asyncio
async def test_fuzzy_low_confidence_open_exception(async_client: AsyncClient, db_session: AsyncSession):
    """
    Test that low confidence discrepancy (date > 7 days or completely different description/amount)
    becomes an OPEN exception without auto-match.
    """
    org, user, token = await setup_org_and_user(db_session, "Exception Org")
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": str(org.id)}

    stmt_csv = "Date,Description,Amount\n2026-08-01,Unrelated Wire Outflow,3400.00\n"
    ledg_csv = "Date,Description,Amount\n2026-08-28,Completely Different Receipt,890.00\n"

    res_s = await async_client.post("/api/v1/uploads/statement", headers=headers, files={"file": ("s.csv", io.BytesIO(stmt_csv.encode("utf-8")), "text/csv")})
    res_l = await async_client.post("/api/v1/uploads/ledger", headers=headers, files={"file": ("l.csv", io.BytesIO(ledg_csv.encode("utf-8")), "text/csv")})

    res_run = await async_client.post(
        "/api/v1/reconcile/run",
        headers=headers,
        json={"statement_upload_id": res_s.json()["upload_id"], "ledger_upload_id": res_l.json()["upload_id"]},
    )
    run_id = uuid.UUID(res_run.json()["run_id"])

    res_poll = await async_client.get(f"/api/v1/reconcile/{run_id}", headers=headers)
    data = res_poll.json()
    assert data["status"] == "complete"
    assert data["matched_count"] == 0
    assert data["exception_count"] == 2

    # Verify ReconciliationException has status OPEN
    e_stmt = select(ReconciliationException).where(ReconciliationException.reconciliation_run_id == run_id)
    e_res = await db_session.execute(e_stmt)
    exceptions = list(e_res.scalars().all())
    assert len(exceptions) == 2
    assert all(e.status == ExceptionStatus.OPEN for e in exceptions)
