"""
Tests for Part 10: AI Financial Assistant (Ask Endpoint)
Verifies:
  - POST /api/v1/ask endpoint functionality
  - Intent classification & safe scoped data retrieval
  - Real database records returned in supporting_rows
  - LLM provider abstraction & deterministic fallback synthesis
  - Audit logging of AI requests
  - Cross-tenant organization isolation
  - Error and empty state handling
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models import (
    AuditLog,
    ExceptionPriority,
    ExceptionStatus,
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
from app.services.llm_provider import LLMProvider


class MockCustomLLMProvider(LLMProvider):
    """Custom mock provider for testing LLM response integration."""

    def __init__(self, canned_response: str):
        self.canned_response = canned_response

    async def generate_response(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        return self.canned_response


class FailingLLMProvider(LLMProvider):
    """Provider simulating network failure / timeout."""

    async def generate_response(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        raise RuntimeError("Simulated LLM API Timeout or Network Disconnect")


async def _setup_ask_context(db: AsyncSession, org_name: str = "Ask Org"):
    """Set up organization with full financial data context for AI queries."""
    org = Organization(id=uuid.uuid4(), name=org_name, slug=f"slug-{uuid.uuid4().hex[:8]}")
    user = User(
        id=uuid.uuid4(),
        email=f"analyst-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hash",
        full_name="Financial Analyst",
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
        total_transactions=10, matched_count=8, exception_count=2, pending_review_count=0,
        total_value_reconciled=Decimal("15400.00"), average_confidence=Decimal("0.9650"),
        created_by=user.id,
        started_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
    )
    db.add(run)
    await db.flush()

    tx_exc1 = Transaction(
        id=uuid.uuid4(), organization_id=org.id, upload_id=u_stmt.id,
        reconciliation_run_id=run.id, source=TransactionSource.STATEMENT,
        transaction_date=datetime(2026, 8, 5, tzinfo=timezone.utc),
        description="Wire Transfer - Vendor Global Inc",
        amount=Decimal("12500.0000"), currency="USD",
        status=TransactionStatus.EXCEPTION,
        raw_data={},
    )
    tx_exc2 = Transaction(
        id=uuid.uuid4(), organization_id=org.id, upload_id=u_stmt.id,
        reconciliation_run_id=run.id, source=TransactionSource.STATEMENT,
        transaction_date=datetime(2026, 8, 7, tzinfo=timezone.utc),
        description="Subscription Fee SaaS Monthly",
        amount=Decimal("450.0000"), currency="USD",
        status=TransactionStatus.EXCEPTION,
        raw_data={},
    )
    db.add_all([tx_exc1, tx_exc2])
    await db.flush()

    exc1 = ReconciliationException(
        id=uuid.uuid4(), organization_id=org.id, reconciliation_run_id=run.id,
        transaction_id=tx_exc1.id, best_candidate_transaction_id=None,
        reason_text="Unmatched Statement: No counterparty found for USD 12500.00",
        priority=ExceptionPriority.HIGH, status=ExceptionStatus.OPEN,
    )
    exc2 = ReconciliationException(
        id=uuid.uuid4(), organization_id=org.id, reconciliation_run_id=run.id,
        transaction_id=tx_exc2.id, best_candidate_transaction_id=None,
        reason_text="Unmatched Subscription: Counterpart missing in ledger",
        priority=ExceptionPriority.MEDIUM, status=ExceptionStatus.OPEN,
    )
    db.add_all([exc1, exc2])
    await db.commit()

    token = create_access_token(user_id=user.id)
    return {
        "org": org, "user": user, "token": token, "run": run,
        "tx_exc1": tx_exc1, "tx_exc2": tx_exc2, "exc1": exc1, "exc2": exc2,
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  ASK AI FUNCTIONALITY & DOMAINS
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_ask_exceptions_question(async_client: AsyncClient, db_session: AsyncSession):
    """Verify asking about failed/unmatched transactions returns real exception data and supporting rows."""
    ctx = await _setup_ask_context(db_session)
    headers = {"Authorization": f"Bearer {ctx['token']}", "X-Organization-Id": str(ctx["org"].id)}

    payload = {"question": "Which transactions failed to match and why?"}
    res = await async_client.post("/api/v1/ask", headers=headers, json=payload)
    assert res.status_code == 200
    data = res.json()

    assert "answer" in data
    assert len(data["answer"]) > 10
    assert len(data["supporting_rows"]) >= 2

    # Check supporting rows contain actual PostgreSQL exception records
    supporting_types = [r["type"] for r in data["supporting_rows"]]
    assert "exception" in supporting_types

    exc_ids = [r["id"] for r in data["supporting_rows"] if r["type"] == "exception"]
    assert str(ctx["exc1"].id) in exc_ids or str(ctx["exc2"].id) in exc_ids

    # Verify answers reference real amounts without hallucination
    assert "12500" in data["answer"] or "Vendor Global" in data["answer"] or "Subscription" in data["answer"]


@pytest.mark.asyncio
async def test_ask_reconciliation_summary_question(async_client: AsyncClient, db_session: AsyncSession):
    """Verify asking about reconciliation run status returns run metrics."""
    ctx = await _setup_ask_context(db_session)
    headers = {"Authorization": f"Bearer {ctx['token']}", "X-Organization-Id": str(ctx["org"].id)}

    payload = {"question": "What is the status of the latest reconciliation run?"}
    res = await async_client.post("/api/v1/ask", headers=headers, json=payload)
    assert res.status_code == 200
    data = res.json()

    assert "15400" in data["answer"] or "Matched: 8" in data["answer"] or "complete" in data["answer"].lower()
    run_rows = [r for r in data["supporting_rows"] if r["type"] == "reconciliation_run"]
    assert len(run_rows) >= 1
    assert run_rows[0]["id"] == str(ctx["run"].id)


@pytest.mark.asyncio
async def test_ask_high_risk_items_question(async_client: AsyncClient, db_session: AsyncSession):
    """Verify asking about high risk items returns high priority exceptions."""
    ctx = await _setup_ask_context(db_session)
    headers = {"Authorization": f"Bearer {ctx['token']}", "X-Organization-Id": str(ctx["org"].id)}

    payload = {"question": "Are there any high risk or large unreconciled items?"}
    res = await async_client.post("/api/v1/ask", headers=headers, json=payload)
    assert res.status_code == 200
    data = res.json()

    assert "Vendor Global Inc" in data["answer"] or "12500" in data["answer"]


@pytest.mark.asyncio
async def test_ask_forecast_question(async_client: AsyncClient, db_session: AsyncSession):
    """Verify asking about cash forecast triggers forecasting context."""
    ctx = await _setup_ask_context(db_session)
    headers = {"Authorization": f"Bearer {ctx['token']}", "X-Organization-Id": str(ctx["org"].id)}

    payload = {"question": "What is our projected cash balance and runway forecast?"}
    res = await async_client.post("/api/v1/ask", headers=headers, json=payload)
    assert res.status_code == 200
    data = res.json()

    assert "Cash" in data["answer"] or "Forecast" in data["answer"] or "Projected" in data["answer"]


# ═══════════════════════════════════════════════════════════════════════════════
#  LLM PROVIDER ABSTRACTION & FALLBACK
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_ask_with_mock_llm_provider(db_session: AsyncSession):
    """Verify AskService correctly incorporates external LLM provider responses."""
    from app.services.ask_service import AskService

    ctx = await _setup_ask_context(db_session)
    custom_mock = MockCustomLLMProvider("AI Analysis: Identified 2 high-priority breaks in statement file.")

    response = await AskService.process_question(
        db=db_session,
        organization_id=ctx["org"].id,
        user=ctx["user"],
        question="Summarize our breaks",
        llm_provider=custom_mock,
    )
    assert response.answer == "AI Analysis: Identified 2 high-priority breaks in statement file."
    assert len(response.supporting_rows) >= 2


@pytest.mark.asyncio
async def test_ask_with_failing_llm_provider_graceful_fallback(db_session: AsyncSession):
    """Verify that if external LLM times out or fails, AskService falls back to deterministic synthesis."""
    from app.services.ask_service import AskService

    ctx = await _setup_ask_context(db_session)
    failing_mock = FailingLLMProvider()

    # Must NOT throw 500 error; gracefully falls back to deterministic synthesis from real data
    response = await AskService.process_question(
        db=db_session,
        organization_id=ctx["org"].id,
        user=ctx["user"],
        question="Which transactions failed?",
        llm_provider=failing_mock,
    )
    assert "Vendor Global" in response.answer or "active exception" in response.answer
    assert len(response.supporting_rows) >= 2


# ═══════════════════════════════════════════════════════════════════════════════
#  AUDIT LOGGING
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_ask_records_audit_log(async_client: AsyncClient, db_session: AsyncSession):
    """Verify that every Ask AI query creates an audit log entry."""
    ctx = await _setup_ask_context(db_session)
    headers = {"Authorization": f"Bearer {ctx['token']}", "X-Organization-Id": str(ctx["org"].id)}

    res = await async_client.post("/api/v1/ask", headers=headers, json={"question": "Check my breaks"})
    assert res.status_code == 200

    # Query audit logs
    audit_stmt = select(AuditLog).where(
        AuditLog.organization_id == ctx["org"].id,
        AuditLog.action == "ai.ask",
    )
    audit_res = await db_session.execute(audit_stmt)
    logs = list(audit_res.scalars().all())
    assert len(logs) >= 1
    assert logs[-1].actor_id == ctx["user"].id
    assert logs[-1].details["intent"] == "exceptions"


# ═══════════════════════════════════════════════════════════════════════════════
#  ORGANIZATION ISOLATION & VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_cross_tenant_ask_isolation(async_client: AsyncClient, db_session: AsyncSession):
    """Verify Tenant 1 cannot access or see Tenant 2's records via Ask AI."""
    ctx1 = await _setup_ask_context(db_session, "Tenant 1")
    ctx2 = await _setup_ask_context(db_session, "Tenant 2")

    h1 = {"Authorization": f"Bearer {ctx1['token']}", "X-Organization-Id": str(ctx1["org"].id)}

    res1 = await async_client.post("/api/v1/ask", headers=h1, json={"question": "List all exceptions"})
    assert res1.status_code == 200
    data1 = res1.json()

    # All supporting rows must belong strictly to Tenant 1
    retrieved_ids = [r["id"] for r in data1["supporting_rows"]]
    assert str(ctx2["exc1"].id) not in retrieved_ids
    assert str(ctx2["exc2"].id) not in retrieved_ids

    # Spoofed header must be denied
    h_spoof = {"Authorization": f"Bearer {ctx1['token']}", "X-Organization-Id": str(ctx2["org"].id)}
    res_spoof = await async_client.post("/api/v1/ask", headers=h_spoof, json={"question": "List exceptions"})
    assert res_spoof.status_code == 403


@pytest.mark.asyncio
async def test_empty_organization_ask_handling(async_client: AsyncClient, db_session: AsyncSession):
    """Verify empty organization returns an honest response without hallucinations."""
    org = Organization(id=uuid.uuid4(), name="Empty Org", slug="empty-slug")
    user = User(
        id=uuid.uuid4(), email="empty@test.com", password_hash="hash", full_name="Empty User", is_active=True
    )
    db_session.add_all([org, user])
    await db_session.flush()

    m = Membership(id=uuid.uuid4(), organization_id=org.id, user_id=user.id, role=MembershipRole.ANALYST)
    db_session.add(m)
    await db_session.commit()

    token = create_access_token(user_id=user.id)
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": str(org.id)}

    res = await async_client.post("/api/v1/ask", headers=headers, json={"question": "What is our reconcil status?"})
    assert res.status_code == 200
    data = res.json()
    assert len(data["supporting_rows"]) == 0
    assert "No financial records" in data["answer"] or "no" in data["answer"].lower()
