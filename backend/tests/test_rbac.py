import uuid
import pytest
from fastapi import APIRouter, Depends
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_membership, require_roles
from app.core.security import create_access_token
from app.db.session import get_db_session
from app.main import app
from app.models import Membership, MembershipRole, Organization, User

# Create dedicated test routes for verifying RBAC and Multi-Tenancy dependencies
rbac_test_router = APIRouter(prefix="/api/v1/test-rbac")


@rbac_test_router.get("/tenant-data")
async def tenant_data_endpoint(
    membership: Membership = Depends(get_current_membership),
):
    return {
        "organization_id": str(membership.organization_id),
        "user_id": str(membership.user_id),
        "role": membership.role.value,
    }


@rbac_test_router.get("/admin-only")
async def admin_only_endpoint(
    membership: Membership = Depends(require_roles(MembershipRole.ADMIN)),
):
    return {"access": "granted", "role": membership.role.value}


@rbac_test_router.get("/analyst-ops")
async def analyst_ops_endpoint(
    membership: Membership = Depends(require_roles(MembershipRole.ANALYST)),
):
    return {"access": "granted", "role": membership.role.value}


@rbac_test_router.get("/viewer-view")
async def viewer_view_endpoint(
    membership: Membership = Depends(require_roles(MembershipRole.VIEWER)),
):
    return {"access": "granted", "role": membership.role.value}


# Include test router in app for testing
app.include_router(rbac_test_router)


@pytest.mark.asyncio
async def test_unauthenticated_request_rejected(async_client: AsyncClient):
    """Ensure requests without Bearer token are rejected with 401."""
    response = await async_client.get("/api/v1/test-rbac/tenant-data")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_missing_or_invalid_organization_header(async_client: AsyncClient, db_session: AsyncSession):
    """Ensure requests without or with malformed X-Organization-Id header are rejected with 400."""
    user = User(
        id=uuid.uuid4(),
        email="tenant.test@acme.com",
        password_hash="hash",
        full_name="Tenant Test",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    token = create_access_token(user_id=user.id)
    headers = {"Authorization": f"Bearer {token}"}

    # Missing header
    res_missing = await async_client.get("/api/v1/test-rbac/tenant-data", headers=headers)
    assert res_missing.status_code == 400

    # Invalid header format
    res_invalid = await async_client.get(
        "/api/v1/test-rbac/tenant-data",
        headers={**headers, "X-Organization-Id": "invalid-uuid"},
    )
    assert res_invalid.status_code == 400


@pytest.mark.asyncio
async def test_cross_tenant_isolation_blocked(async_client: AsyncClient, db_session: AsyncSession):
    """
    Multi-tenant test:
    User A is in Org 1.
    User A attempts to access Org 2 via X-Organization-Id header.
    Must be blocked with 403 Forbidden.
    """
    user_a = User(
        id=uuid.uuid4(),
        email="usera@org1.com",
        password_hash="hash",
        full_name="User A",
        is_active=True,
    )
    org1 = Organization(id=uuid.uuid4(), name="Org 1", slug="org-1")
    org2 = Organization(id=uuid.uuid4(), name="Org 2", slug="org-2")

    db_session.add_all([user_a, org1, org2])
    await db_session.flush()

    # User A is member of Org 1 ONLY
    m1 = Membership(id=uuid.uuid4(), organization_id=org1.id, user_id=user_a.id, role=MembershipRole.ADMIN)
    db_session.add(m1)
    await db_session.commit()

    token = create_access_token(user_id=user_a.id)

    # Authorized access to Org 1
    res_org1 = await async_client.get(
        "/api/v1/test-rbac/tenant-data",
        headers={"Authorization": f"Bearer {token}", "X-Organization-Id": str(org1.id)},
    )
    assert res_org1.status_code == 200
    assert res_org1.json()["organization_id"] == str(org1.id)

    # Unauthorized access to Org 2 (cross-tenant access) -> 403 Forbidden
    res_org2 = await async_client.get(
        "/api/v1/test-rbac/tenant-data",
        headers={"Authorization": f"Bearer {token}", "X-Organization-Id": str(org2.id)},
    )
    assert res_org2.status_code == 403
    assert "Access denied" in res_org2.json()["detail"]


@pytest.mark.asyncio
async def test_role_based_access_control(async_client: AsyncClient, db_session: AsyncSession):
    """
    RBAC Hierarchy Test:
    - Admin has access to Admin, Analyst, and Viewer routes.
    - Analyst has access to Analyst and Viewer routes, but blocked on Admin routes.
    - Viewer has access to Viewer routes, but blocked on Analyst and Admin routes.
    """
    org = Organization(id=uuid.uuid4(), name="RBAC Org", slug="rbac-org")
    admin_user = User(id=uuid.uuid4(), email="admin@rbac.com", password_hash="hash", full_name="Admin", is_active=True)
    analyst_user = User(id=uuid.uuid4(), email="analyst@rbac.com", password_hash="hash", full_name="Analyst", is_active=True)
    viewer_user = User(id=uuid.uuid4(), email="viewer@rbac.com", password_hash="hash", full_name="Viewer", is_active=True)

    db_session.add_all([org, admin_user, analyst_user, viewer_user])
    await db_session.flush()

    m_admin = Membership(id=uuid.uuid4(), organization_id=org.id, user_id=admin_user.id, role=MembershipRole.ADMIN)
    m_analyst = Membership(id=uuid.uuid4(), organization_id=org.id, user_id=analyst_user.id, role=MembershipRole.ANALYST)
    m_viewer = Membership(id=uuid.uuid4(), organization_id=org.id, user_id=viewer_user.id, role=MembershipRole.VIEWER)

    db_session.add_all([m_admin, m_analyst, m_viewer])
    await db_session.commit()

    admin_headers = {
        "Authorization": f"Bearer {create_access_token(admin_user.id)}",
        "X-Organization-Id": str(org.id),
    }
    analyst_headers = {
        "Authorization": f"Bearer {create_access_token(analyst_user.id)}",
        "X-Organization-Id": str(org.id),
    }
    viewer_headers = {
        "Authorization": f"Bearer {create_access_token(viewer_user.id)}",
        "X-Organization-Id": str(org.id),
    }

    # 1. Admin tests: Can access Admin, Analyst, Viewer
    assert (await async_client.get("/api/v1/test-rbac/admin-only", headers=admin_headers)).status_code == 200
    assert (await async_client.get("/api/v1/test-rbac/analyst-ops", headers=admin_headers)).status_code == 200
    assert (await async_client.get("/api/v1/test-rbac/viewer-view", headers=admin_headers)).status_code == 200

    # 2. Analyst tests: Can access Analyst and Viewer, Blocked on Admin (403)
    assert (await async_client.get("/api/v1/test-rbac/admin-only", headers=analyst_headers)).status_code == 403
    assert (await async_client.get("/api/v1/test-rbac/analyst-ops", headers=analyst_headers)).status_code == 200
    assert (await async_client.get("/api/v1/test-rbac/viewer-view", headers=analyst_headers)).status_code == 200

    # 3. Viewer tests: Can access Viewer, Blocked on Analyst (403) and Admin (403)
    assert (await async_client.get("/api/v1/test-rbac/admin-only", headers=viewer_headers)).status_code == 403
    assert (await async_client.get("/api/v1/test-rbac/analyst-ops", headers=viewer_headers)).status_code == 403
    assert (await async_client.get("/api/v1/test-rbac/viewer-view", headers=viewer_headers)).status_code == 200
