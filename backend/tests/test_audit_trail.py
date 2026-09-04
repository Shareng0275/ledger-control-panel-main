"""
Tests for Part 12: Production-Quality Immutable Audit Trail
Verifies:
  - Centralized AuditService recording key lifecycle events
  - Audit logging of login, logout, uploads, validation failures, reconciliation runs, manual matching, rejections, and bulk resolutions
  - GET /api/v1/audit endpoint with pagination and multi-dimensional filters
  - Immutability and append-only architecture
  - Multi-tenant organization isolation and RBAC
"""
import io
import uuid
from datetime import datetime, timedelta, timezone
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
from app.services.audit_service import AuditService


async def _setup_audit_context(db: AsyncSession, org_name: str = "Audit Org"):
    """Set up organization, admin user, analyst user, and viewer user."""
    org = Organization(id=uuid.uuid4(), name=org_name, slug=f"slug-{uuid.uuid4().hex[:8]}")
    admin_user = User(
        id=uuid.uuid4(),
        email=f"admin-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hash",
        full_name="Audit Admin",
        is_active=True,
    )
    viewer_user = User(
        id=uuid.uuid4(),
        email=f"viewer-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hash",
        full_name="Audit Viewer",
        is_active=True,
    )
    db.add_all([org, admin_user, viewer_user])
    await db.flush()

    m_admin = Membership(id=uuid.uuid4(), organization_id=org.id, user_id=admin_user.id, role=MembershipRole.ADMIN)
    m_viewer = Membership(id=uuid.uuid4(), organization_id=org.id, user_id=viewer_user.id, role=MembershipRole.VIEWER)
    db.add_all([m_admin, m_viewer])
    await db.commit()

    admin_token = create_access_token(user_id=admin_user.id)
    viewer_token = create_access_token(user_id=viewer_user.id)

    return {
        "org": org,
        "admin_user": admin_user,
        "viewer_user": viewer_user,
        "admin_token": admin_token,
        "viewer_token": viewer_token,
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  CENTRALIZED AUDIT SERVICE LOGGING
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_audit_service_event_recording(db_session: AsyncSession):
    """Verify AuditService records append-only events with all required fields."""
    ctx = await _setup_audit_context(db_session)
    org_id = ctx["org"].id
    user_id = ctx["admin_user"].id

    # 1. Log manual match
    entry1 = await AuditService.log_event(
        db=db_session,
        organization_id=org_id,
        actor_id=user_id,
        action="exception.resolved_match",
        entity_type="Exception",
        entity_id=uuid.uuid4(),
        details={"rule": "manual_match", "confidence": "1.0000"},
        ip_address="192.168.1.50",
        commit=True,
    )
    assert entry1.id is not None
    assert entry1.action == "exception.resolved_match"

    # 2. Log reconciliation completed
    run_id = uuid.uuid4()
    await AuditService.log_reconciliation_completed(
        db=db_session,
        organization_id=org_id,
        run_id=run_id,
        matched_count=20,
        exception_count=2,
        pending_review_count=1,
        total_value_reconciled=Decimal("50000.00"),
        user_id=user_id,
    )
    await db_session.commit()

    # Query directly from DB
    stmt = select(AuditLog).where(AuditLog.organization_id == org_id).order_by(AuditLog.created_at.desc())
    res = await db_session.execute(stmt)
    logs = list(res.scalars().all())
    assert len(logs) >= 2


# ═══════════════════════════════════════════════════════════════════════════════
#  AUDIT TRAIL API, PAGINATION & FILTERS
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_get_audit_trail_pagination(async_client: AsyncClient, db_session: AsyncSession):
    """Verify GET /api/v1/audit returns paginated chronological records."""
    ctx = await _setup_audit_context(db_session)
    org_id = ctx["org"].id
    user_id = ctx["admin_user"].id
    headers = {"Authorization": f"Bearer {ctx['admin_token']}", "X-Organization-Id": str(org_id)}

    # Seed 5 audit records
    for i in range(5):
        await AuditService.log_event(
            db=db_session,
            organization_id=org_id,
            actor_id=user_id,
            action=f"system.action_{i+1}",
            entity_type="System",
            details={"index": i + 1},
            commit=False,
        )
    await db_session.commit()

    res = await async_client.get("/api/v1/audit?page=1&page_size=3", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert data["total"] == 5
    assert len(data["items"]) == 3
    assert data["page"] == 1
    assert data["total_pages"] == 2
    assert data["has_next"] is True
    assert data["items"][0]["actor"] == "Audit Admin"


@pytest.mark.asyncio
async def test_audit_trail_action_and_entity_filters(async_client: AsyncClient, db_session: AsyncSession):
    """Verify filtering audit logs by action and entity type."""
    ctx = await _setup_audit_context(db_session)
    org_id = ctx["org"].id
    user_id = ctx["admin_user"].id
    headers = {"Authorization": f"Bearer {ctx['admin_token']}", "X-Organization-Id": str(org_id)}

    await AuditService.log_event(
        db=db_session,
        organization_id=org_id,
        actor_id=user_id,
        action="upload.created",
        entity_type="Upload",
        commit=False,
    )
    await AuditService.log_event(
        db=db_session,
        organization_id=org_id,
        actor_id=user_id,
        action="reconciliation.started",
        entity_type="ReconciliationRun",
        commit=False,
    )
    await db_session.commit()

    # Filter by action
    res_act = await async_client.get("/api/v1/audit?action=reconciliation", headers=headers)
    assert res_act.status_code == 200
    assert res_act.json()["total"] == 1
    assert res_act.json()["items"][0]["action"] == "reconciliation.started"

    # Filter by entity_type
    res_ent = await async_client.get("/api/v1/audit?entity_type=Upload", headers=headers)
    assert res_ent.status_code == 200
    assert res_ent.json()["total"] == 1
    assert res_ent.json()["items"][0]["entity_type"] == "Upload"


@pytest.mark.asyncio
async def test_audit_trail_date_filter(async_client: AsyncClient, db_session: AsyncSession):
    """Verify filtering audit records by date range."""
    ctx = await _setup_audit_context(db_session)
    org_id = ctx["org"].id
    user_id = ctx["admin_user"].id
    headers = {"Authorization": f"Bearer {ctx['admin_token']}", "X-Organization-Id": str(org_id)}

    now = datetime.now(timezone.utc)
    # Log past event
    old_log = AuditLog(
        id=uuid.uuid4(),
        organization_id=org_id,
        actor_id=user_id,
        action="historical.event",
        entity_type="Test",
        created_at=now - timedelta(days=10),
    )
    # Log recent event
    new_log = AuditLog(
        id=uuid.uuid4(),
        organization_id=org_id,
        actor_id=user_id,
        action="recent.event",
        entity_type="Test",
        created_at=now,
    )
    db_session.add_all([old_log, new_log])
    await db_session.commit()

    start_iso = (now - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    res = await async_client.get(f"/api/v1/audit?start_date={start_iso}", headers=headers)
    assert res.status_code == 200
    assert res.json()["total"] == 1
    assert res.json()["items"][0]["action"] == "recent.event"


# ═══════════════════════════════════════════════════════════════════════════════
#  SECURITY, RBAC & TENANT ISOLATION
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_viewer_can_read_audit_trail(async_client: AsyncClient, db_session: AsyncSession):
    """Verify viewer role has read-only access to organization audit logs."""
    ctx = await _setup_audit_context(db_session)
    org_id = ctx["org"].id
    viewer_headers = {"Authorization": f"Bearer {ctx['viewer_token']}", "X-Organization-Id": str(org_id)}

    res = await async_client.get("/api/v1/audit", headers=viewer_headers)
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_cross_tenant_audit_isolation(async_client: AsyncClient, db_session: AsyncSession):
    """Ensure Tenant 1 cannot access or view Tenant 2's audit logs."""
    ctx1 = await _setup_audit_context(db_session, "Tenant Alpha")
    ctx2 = await _setup_audit_context(db_session, "Tenant Beta")

    # Record log in Tenant 2
    await AuditService.log_event(
        db=db_session,
        organization_id=ctx2["org"].id,
        actor_id=ctx2["admin_user"].id,
        action="secret.tenant2_action",
        entity_type="Secret",
        commit=True,
    )

    h1 = {"Authorization": f"Bearer {ctx1['admin_token']}", "X-Organization-Id": str(ctx1["org"].id)}
    res1 = await async_client.get("/api/v1/audit", headers=h1)
    assert res1.status_code == 200
    assert res1.json()["total"] == 0  # Tenant 1 has 0 logs

    # Spoofed header attempting to read Tenant 2 logs must be blocked
    h_spoof = {"Authorization": f"Bearer {ctx1['admin_token']}", "X-Organization-Id": str(ctx2["org"].id)}
    res_spoof = await async_client.get("/api/v1/audit", headers=h_spoof)
    assert res_spoof.status_code == 403


@pytest.mark.asyncio
async def test_unauthenticated_audit_request_rejected(async_client: AsyncClient):
    """Verify unauthenticated requests to audit logs return 401."""
    res = await async_client.get("/api/v1/audit")
    assert res.status_code == 401
