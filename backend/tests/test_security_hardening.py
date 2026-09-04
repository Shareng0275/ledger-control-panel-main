"""
Tests for Part 13: Security + Production Hardening
Verifies:
  - HTTP Security Headers (X-Content-Type-Options, X-Frame-Options, CSP, etc.)
  - Secure CORS configuration
  - Rate limiting protection (HTTP 429)
  - Comprehensive Multi-Tenant IDOR protection across all entity types
  - SQL injection immunity on filters, search, and sorting
  - Safe error responses (no stack traces, database credentials, or internal details)
  - Secret & Password confidentiality
"""
import io
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.rate_limiter import SlidingWindowRateLimiter
from app.core.security import create_access_token, verify_password
from app.models import (
    AuditLog,
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


async def _create_tenant_environment(db: AsyncSession, name_prefix: str = "SecOrg"):
    """Create an isolated organization, user, and full dataset for security testing."""
    org = Organization(id=uuid.uuid4(), name=f"{name_prefix} Org", slug=f"slug-{uuid.uuid4().hex[:8]}")
    user = User(
        id=uuid.uuid4(),
        email=f"user-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="$argon2id$v=19$m=65536,t=3,p=4$somehash",
        full_name=f"{name_prefix} User",
        is_active=True,
    )
    db.add_all([org, user])
    await db.flush()

    membership = Membership(id=uuid.uuid4(), organization_id=org.id, user_id=user.id, role=MembershipRole.ADMIN)
    db.add(membership)

    upload = Upload(
        id=uuid.uuid4(),
        organization_id=org.id,
        filename="stmt.csv",
        upload_type=UploadType.STATEMENT,
        storage_path="u/stmt.csv",
        status=UploadStatus.VALID,
    )
    db.add(upload)
    await db.flush()

    run = ReconciliationRun(
        id=uuid.uuid4(),
        organization_id=org.id,
        statement_upload_id=upload.id,
        status=ReconciliationStatus.COMPLETE,
        total_transactions=2,
        matched_count=1,
        exception_count=1,
        pending_review_count=0,
        total_value_reconciled=Decimal("1000.00"),
        created_by=user.id,
    )
    db.add(run)
    await db.flush()

    tx = Transaction(
        id=uuid.uuid4(),
        organization_id=org.id,
        upload_id=upload.id,
        reconciliation_run_id=run.id,
        source=TransactionSource.STATEMENT,
        transaction_date=datetime(2026, 8, 1, tzinfo=timezone.utc),
        description="Confidential Internal Transfer",
        amount=Decimal("1000.0000"),
        currency="USD",
        status=TransactionStatus.EXCEPTION,
        raw_data={"secret_client_id": "CLIENT-XYZ-999"},
    )
    db.add(tx)
    await db.flush()

    exc = ReconciliationException(
        id=uuid.uuid4(),
        organization_id=org.id,
        reconciliation_run_id=run.id,
        transaction_id=tx.id,
        reason_text="Unmatched secret break",
        priority=ExceptionPriority.HIGH,
        status=ExceptionStatus.OPEN,
    )
    db.add(exc)

    audit = AuditLog(
        id=uuid.uuid4(),
        organization_id=org.id,
        actor_id=user.id,
        action="admin.secret_action",
        entity_type="Transaction",
        entity_id=tx.id,
        details={"confidential": "value"},
    )
    db.add(audit)
    await db.commit()

    token = create_access_token(user_id=user.id)
    return {
        "org": org,
        "user": user,
        "token": token,
        "upload": upload,
        "run": run,
        "tx": tx,
        "exc": exc,
        "audit": audit,
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  1. SECURITY HEADERS & CORS
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_security_headers_present_on_all_responses(async_client: AsyncClient):
    """Verify standard HTTP production security headers are appended to responses."""
    res = await async_client.get("/health")
    assert res.status_code == 200

    headers = res.headers
    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "DENY"
    assert headers.get("X-XSS-Protection") == "1; mode=block"
    assert headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "Content-Security-Policy" in headers
    assert "Permissions-Policy" in headers


@pytest.mark.asyncio
async def test_cors_origin_headers(async_client: AsyncClient):
    """Verify CORS preflight headers properly reflect allowed origins."""
    res = await async_client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert res.status_code in [200, 204]
    assert res.headers.get("access-control-allow-origin") == "http://localhost:5173"


# ═══════════════════════════════════════════════════════════════════════════════
#  2. RATE LIMITING PROTECTION
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_sliding_window_rate_limiter():
    """Verify SlidingWindowRateLimiter correctly throttles when limit is exceeded."""
    limiter = SlidingWindowRateLimiter(requests_per_minute=5, burst_limit=5)
    identifier = "192.168.1.100:test_endpoint"

    # First 5 requests must pass
    for _ in range(5):
        is_limited, _ = limiter.is_rate_limited(identifier)
        assert not is_limited

    # 6th request must be rate-limited
    is_limited, retry_after = limiter.is_rate_limited(identifier)
    assert is_limited
    assert retry_after > 0

    # Reset allows new requests
    limiter.reset()
    is_limited, _ = limiter.is_rate_limited(identifier)
    assert not is_limited


# ═══════════════════════════════════════════════════════════════════════════════
#  3. MULTI-TENANT IDOR PROTECTION ACROSS ALL ENTITY TYPES
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_idor_protection_transactions(async_client: AsyncClient, db_session: AsyncSession):
    """Tenant A cannot access Tenant B's transaction by ID."""
    t_a = await _create_tenant_environment(db_session, "TenantA")
    t_b = await _create_tenant_environment(db_session, "TenantB")

    h_a = {"Authorization": f"Bearer {t_a['token']}", "X-Organization-Id": str(t_a["org"].id)}
    
    # Request Tenant B's transaction with Tenant A's credentials
    res = await async_client.get(f"/api/v1/transactions/{t_b['tx'].id}", headers=h_a)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_idor_protection_exceptions(async_client: AsyncClient, db_session: AsyncSession):
    """Tenant A cannot access or resolve Tenant B's exception."""
    t_a = await _create_tenant_environment(db_session, "TenantA_Exc")
    t_b = await _create_tenant_environment(db_session, "TenantB_Exc")

    h_a = {"Authorization": f"Bearer {t_a['token']}", "X-Organization-Id": str(t_a["org"].id)}

    # Read exception
    res_get = await async_client.get(f"/api/v1/exceptions/{t_b['exc'].id}", headers=h_a)
    assert res_get.status_code == 404

    # Resolve exception
    res_resolve = await async_client.post(
        f"/api/v1/exceptions/{t_b['exc'].id}/resolve",
        headers=h_a,
        json={"action": "reject"},
    )
    assert res_resolve.status_code == 404


@pytest.mark.asyncio
async def test_idor_protection_reconciliation_runs(async_client: AsyncClient, db_session: AsyncSession):
    """Tenant A cannot access Tenant B's reconciliation run or summary."""
    t_a = await _create_tenant_environment(db_session, "TenantA_Run")
    t_b = await _create_tenant_environment(db_session, "TenantB_Run")

    h_a = {"Authorization": f"Bearer {t_a['token']}", "X-Organization-Id": str(t_a["org"].id)}

    res_run = await async_client.get(f"/api/v1/reconcile/{t_b['run'].id}", headers=h_a)
    assert res_run.status_code == 403

    res_sum = await async_client.get(f"/api/v1/reconcile/{t_b['run'].id}/summary", headers=h_a)
    assert res_sum.status_code == 404


@pytest.mark.asyncio
async def test_idor_protection_audit_trail(async_client: AsyncClient, db_session: AsyncSession):
    """Tenant A cannot view Tenant B's audit trail records."""
    t_a = await _create_tenant_environment(db_session, "TenantA_Audit")
    t_b = await _create_tenant_environment(db_session, "TenantB_Audit")

    h_a = {"Authorization": f"Bearer {t_a['token']}", "X-Organization-Id": str(t_a["org"].id)}

    res = await async_client.get(f"/api/v1/audit?entity_id={t_b['audit'].id}", headers=h_a)
    assert res.status_code == 200
    assert res.json()["total"] == 0


# ═══════════════════════════════════════════════════════════════════════════════
#  4. SQL INJECTION IMMUNITY
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_sql_injection_on_transaction_search(async_client: AsyncClient, db_session: AsyncSession):
    """Verify transactions endpoint safely neutralizes SQL injection payloads in search and sort parameters."""
    t_a = await _create_tenant_environment(db_session, "Tenant_SQLi")
    h_a = {"Authorization": f"Bearer {t_a['token']}", "X-Organization-Id": str(t_a["org"].id)}

    sqli_payloads = [
        "' OR 1=1 --",
        "'; DROP TABLE transactions; --",
        "admin'--",
        "UNION SELECT * FROM users--",
    ]

    for payload in sqli_payloads:
        res = await async_client.get(f"/api/v1/transactions?search={payload}", headers=h_a)
        assert res.status_code == 200
        # Results should simply be 0 (no records matching the literal string)
        assert res.json()["total"] == 0

        # Test malicious sort column (falls back to default safely)
        res_sort = await async_client.get(f"/api/v1/transactions?sort_by={payload}", headers=h_a)
        assert res_sort.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════════
#  5. ERROR SECURITY & SECRET PROTECTION
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_safe_error_responses_no_stack_traces(async_client: AsyncClient):
    """Verify global error handlers return safe JSON messages without leaking tracebacks."""
    # 404 Not Found
    res_404 = await async_client.get("/api/v1/non_existent_endpoint_xyz")
    assert res_404.status_code == 404
    data_404 = res_404.json()
    assert "error" in data_404
    assert "Traceback" not in str(data_404)
    assert "postgres" not in str(data_404).lower()

    # 422 Validation Error
    res_422 = await async_client.post("/api/v1/auth/login", json={"invalid_json": True})
    assert res_422.status_code == 422
    data_422 = res_422.json()
    assert data_422["error"] == "ValidationError"
    assert "Traceback" not in str(data_422)


@pytest.mark.asyncio
async def test_password_and_secret_confidentiality(async_client: AsyncClient, db_session: AsyncSession):
    """Verify passwords and secret keys are never exposed in user profiles or API outputs."""
    t_a = await _create_tenant_environment(db_session, "Tenant_Secret")
    h_a = {"Authorization": f"Bearer {t_a['token']}"}

    res_me = await async_client.get("/api/v1/auth/me", headers=h_a)
    assert res_me.status_code == 200
    user_data = res_me.json()

    # Ensure password hash is absent
    assert "password" not in user_data
    assert "password_hash" not in user_data

    # Ensure settings secret strings are masked
    assert "secret" not in settings.SECRET_KEY.get_secret_value().lower() or "replace" in settings.SECRET_KEY.get_secret_value()
    assert str(settings.SECRET_KEY) == "**********"
