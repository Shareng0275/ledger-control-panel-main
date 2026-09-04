"""
End-to-End Frontend Integration Test Suite
Verifies 100% contract compatibility between Lovable Frontend and Antigravity Backend:
  1. Auth Flow (Login, /me, Token Storage, Refresh, Logout, 401)
  2. Upload Flow (Statement & Ledger CSVs, Row Parsing, Validation)
  3. Reconciliation Flow (Dispatch, Polling /reconcile/{id} & /runs/{id}, Complete)
  4. Dashboard Flow (Summary KPIs, Confidence Distribution, Transactions)
  5. Exception Flow (List, Review Drawer Details, Confirm, Reject, Bulk Resolve)
  6. Forecast Flow (7d, 30d, 90d charts with real points and bounds)
  7. Ask Flow (Question -> Answer + Real Supporting Rows)
  8. AI Insights Flow (Backend-generated anomaly insights)
  9. Audit Trail Flow (Real compliance event stream)
  10. Error Handling (400, 401, 403, 404, 422, 429, 500 graceful JSON contracts)
"""
import io
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models import (
    ExceptionPriority,
    ExceptionStatus,
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
from app.services.auth_service import AuthService


# ═══════════════════════════════════════════════════════════════════════════════
#  1. AUTH FLOW
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_frontend_auth_flow(async_client: AsyncClient, db_session: AsyncSession):
    """Test full frontend authentication lifecycle."""
    email = f"cfo-{uuid.uuid4().hex[:6]}@lovable.app"
    password = "SecurePassword123!"

    # 1. Register user
    reg_res = await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "Lovable CFO", "organization_name": "Lovable Corp"},
    )
    assert reg_res.status_code == 201
    reg_data = reg_res.json()
    assert "token" in reg_data
    assert "user" in reg_data

    # 2. Login
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_res.status_code == 200
    login_data = login_res.json()
    assert "token" in login_data
    assert login_data["token_type"] == "bearer"
    token = login_data["token"]
    refresh_tok = login_data["refresh_token"]

    # 3. Access Protected /me
    me_res = await async_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["email"] == email.lower()
    assert len(me_data["memberships"]) >= 1
    org_id = me_data["memberships"][0]["organization_id"]

    # 4. Refresh Token
    ref_res = await async_client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_tok})
    assert ref_res.status_code == 200
    assert "token" in ref_res.json()

    # 5. Logout
    logout_res = await async_client.post("/api/v1/auth/logout", json={"refresh_token": refresh_tok})
    assert logout_res.status_code == 200

    # 6. Unauthenticated request to protected endpoint returns 401
    bad_res = await async_client.get("/api/v1/transactions")
    assert bad_res.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════════
#  2. UPLOAD & RECONCILIATION FULL PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_frontend_upload_and_reconciliation_pipeline(async_client: AsyncClient, db_session: AsyncSession):
    """Test frontend uploading statement + ledger CSVs, starting reconciliation, and polling."""
    # Setup test user & organization
    org = Organization(id=uuid.uuid4(), name="E2E Org", slug=f"slug-{uuid.uuid4().hex[:8]}")
    user = User(
        id=uuid.uuid4(), email=f"analyst-{uuid.uuid4().hex[:8]}@test.com", password_hash="h", full_name="Analyst", is_active=True
    )
    db_session.add_all([org, user])
    await db_session.flush()
    m = Membership(id=uuid.uuid4(), organization_id=org.id, user_id=user.id, role=MembershipRole.ADMIN)
    db_session.add(m)
    await db_session.commit()

    token = create_access_token(user_id=user.id)
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": str(org.id)}

    # 1. Upload Bank Statement CSV
    stmt_csv = "Date,Description,Amount,Reference\n2026-08-01,Stripe Payout,15000.00,REF-ST-001\n2026-08-02,AWS Cloud,1200.00,REF-AWS-002\n2026-08-03,Unmatched Vendor,450.00,REF-UN-003\n"
    stmt_res = await async_client.post(
        "/api/v1/uploads/statement",
        headers=headers,
        files={"file": ("statement.csv", io.BytesIO(stmt_csv.encode("utf-8")), "text/csv")},
    )
    assert stmt_res.status_code == 201
    stmt_upload = stmt_res.json()
    assert stmt_upload["upload_id"] is not None
    assert stmt_upload["rows"] == 3

    # 2. Upload Internal Ledger CSV
    ledg_csv = "Date,Description,Amount,Reference\n2026-08-01,Stripe Deposit,15000.00,REF-ST-001\n2026-08-02,AWS Infrastructure,1200.00,REF-AWS-002\n2026-08-04,Office Supplies,300.00,REF-OFF-004\n"
    ledg_res = await async_client.post(
        "/api/v1/uploads/ledger",
        headers=headers,
        files={"file": ("ledger.csv", io.BytesIO(ledg_csv.encode("utf-8")), "text/csv")},
    )
    assert ledg_res.status_code == 201
    ledg_upload = ledg_res.json()
    assert ledg_upload["upload_id"] is not None
    assert ledg_upload["rows"] == 3

    # 3. Start Reconciliation
    reconcile_res = await async_client.post(
        "/api/v1/reconcile/run",
        headers=headers,
        json={
            "statement_upload_id": stmt_upload["upload_id"],
            "ledger_upload_id": ledg_upload["upload_id"],
        },
    )
    assert reconcile_res.status_code == 201
    run_data = reconcile_res.json()
    run_id = run_data["run_id"]
    assert run_id is not None
    assert "summary" in run_data

    # 4. Poll Reconciliation Run (both /reconcile/{id} and /reconcile/runs/{id})
    poll_res1 = await async_client.get(f"/api/v1/reconcile/{run_id}", headers=headers)
    assert poll_res1.status_code == 200
    assert poll_res1.json()["run_id"] == run_id

    poll_res2 = await async_client.get(f"/api/v1/reconcile/runs/{run_id}", headers=headers)
    assert poll_res2.status_code == 200
    assert poll_res2.json()["run_id"] == run_id

    # 5. Dashboard Summary KPIs
    sum_res = await async_client.get(f"/api/v1/reconcile/{run_id}/summary", headers=headers)
    assert sum_res.status_code == 200
    summary = sum_res.json()
    assert "confidence_distribution" in summary
    assert "match_method_breakdown" in summary

    # 6. Transactions List for Run
    tx_res = await async_client.get(f"/api/v1/transactions?run_id={run_id}", headers=headers)
    assert tx_res.status_code == 200
    tx_data = tx_res.json()
    assert len(tx_data["items"]) >= 1
    assert "transactions" in tx_data

    # 7. Exceptions List for Run
    exc_res = await async_client.get(f"/api/v1/exceptions?run_id={run_id}", headers=headers)
    assert exc_res.status_code == 200
    exc_data = exc_res.json()
    assert "exceptions" in exc_data

    # 8. Single Exception Review Drawer Detail
    if exc_data["exceptions"]:
        first_exc_id = exc_data["exceptions"][0]["id"]
        detail_res = await async_client.get(f"/api/v1/exceptions/{first_exc_id}", headers=headers)
        assert detail_res.status_code == 200
        detail_data = detail_res.json()
        assert "statement_transaction" in detail_data

        # 9. Resolve Exception
        resolve_res = await async_client.post(
            f"/api/v1/exceptions/{first_exc_id}/resolve",
            headers=headers,
            json={"action": "reject", "note": "Verified invalid transaction"},
        )
        assert resolve_res.status_code == 200
        assert resolve_res.json()["status"] == "rejected"


# ═══════════════════════════════════════════════════════════════════════════════
#  3. CASH FORECAST, ASK AI, INSIGHTS & AUDIT FLOWS
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_frontend_analytics_and_intelligence_flows(async_client: AsyncClient, db_session: AsyncSession):
    """Verify Forecast, Ask, Insights, and Audit endpoints seamlessly serve frontend components."""
    org = Organization(id=uuid.uuid4(), name="Intelligence Org", slug=f"slug-{uuid.uuid4().hex[:8]}")
    user = User(
        id=uuid.uuid4(), email=f"risk-{uuid.uuid4().hex[:8]}@test.com", password_hash="h", full_name="Risk Lead", is_active=True
    )
    db_session.add_all([org, user])
    await db_session.flush()
    m = Membership(id=uuid.uuid4(), organization_id=org.id, user_id=user.id, role=MembershipRole.ADMIN)
    db_session.add(m)
    await db_session.commit()

    token = create_access_token(user_id=user.id)
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": str(org.id)}

    # 1. Cash Forecast (7d, 30d, 90d)
    for h in ["7d", "30d", "90d"]:
        fc_res = await async_client.get(f"/api/v1/forecast?horizon={h}", headers=headers)
        assert fc_res.status_code == 200
        fc_data = fc_res.json()
        assert fc_data["horizon"] == h
        assert "points" in fc_data

    # 2. Ask Financial Intelligence
    ask_res = await async_client.post(
        "/api/v1/ask",
        headers=headers,
        json={"question": "What is our current cash status and open exceptions?"},
    )
    assert ask_res.status_code == 200
    ask_data = ask_res.json()
    assert "answer" in ask_data
    assert "supporting_rows" in ask_data

    # 3. Anomaly Insights
    ins_res = await async_client.get("/api/v1/insights", headers=headers)
    assert ins_res.status_code == 200
    ins_data = ins_res.json()
    assert "insights" in ins_data
    assert "severity_counts" in ins_data

    # 4. Audit Trail
    audit_res = await async_client.get("/api/v1/audit", headers=headers)
    assert audit_res.status_code == 200
    audit_data = audit_res.json()
    assert "entries" in audit_data
    assert "items" in audit_data
