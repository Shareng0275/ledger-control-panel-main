import uuid
from datetime import datetime, timezone
from decimal import Decimal
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import create_access_token
from app.models import Membership, MembershipRole, Organization, Transaction, TransactionSource, TransactionStatus, Upload, UploadStatus, UploadType, User


@pytest.mark.asyncio
async def test_health_endpoints(async_client: AsyncClient):
    """Verify both /health and /api/v1/health return 200 with standard status."""
    res_root = await async_client.get("/health")
    assert res_root.status_code == 200
    data_root = res_root.json()
    assert data_root["app_name"] == "Ledger Control API"
    assert "status" in data_root

    res_v1 = await async_client.get("/api/v1/health")
    assert res_v1.status_code == 200
    assert res_v1.json()["app_name"] == "Ledger Control API"


@pytest.mark.asyncio
async def test_openapi_schema_generation(async_client: AsyncClient):
    """Verify OpenAPI schema generates properly and includes domain tags."""
    response = await async_client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "Ledger Control API"
    assert "paths" in schema
    assert "/api/v1/transactions" in schema["paths"]
    assert "/api/v1/auth/login" in schema["paths"]
    assert "/api/v1/reconcile/run" in schema["paths"]
    assert "/api/v1/exceptions" in schema["paths"]
    assert "/api/v1/forecast" in schema["paths"]
    assert "/api/v1/ask" in schema["paths"]
    assert "/api/v1/audit" in schema["paths"]
    assert "/api/v1/insights" in schema["paths"]


@pytest.mark.asyncio
async def test_global_error_handling_404(async_client: AsyncClient):
    """Verify non-existent route returns standard 404 error format without stack trace."""
    response = await async_client.get("/api/v1/non-existent-route")
    assert response.status_code == 404
    data = response.json()
    assert data["status_code"] == 404
    assert data["error"] == "NotFound"


@pytest.mark.asyncio
async def test_global_error_handling_422_validation(async_client: AsyncClient):
    """Verify malformed JSON or validation errors return standard 422 format."""
    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "not-an-email"},  # Missing password, invalid email
    )
    assert response.status_code == 422
    data = response.json()
    assert data["status_code"] == 422
    assert data["error"] == "ValidationError"
    assert "errors" in data


@pytest.mark.asyncio
async def test_frontend_login_contract(async_client: AsyncClient):
    """Verify login response matches Lovable frontend contract (token & user fields)."""
    reg_res = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "contract.user@acme.com",
            "password": "SecurePassword123!",
            "full_name": "Contract User",
            "organization_name": "Contract Org",
        },
    )
    assert reg_res.status_code == 201

    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "contract.user@acme.com", "password": "SecurePassword123!"},
    )
    assert login_res.status_code == 200
    body = login_res.json()
    # Ensure frontend properties exist
    assert "token" in body
    assert "access_token" in body
    assert body["token"] == body["access_token"]
    assert "user" in body
    assert body["user"]["email"] == "contract.user@acme.com"
    assert body["user"]["full_name"] == "Contract User"


@pytest.mark.asyncio
async def test_transactions_pagination_and_filtering(
    async_client: AsyncClient, db_session: AsyncSession
):
    """
    Test Transactions API:
    - Pagination (page, page_size, total, total_pages)
    - Search by description
    - Filter by status
    - Safe sorting by amount
    """
    org = Organization(id=uuid.uuid4(), name="Tx Org", slug="tx-org")
    user = User(
        id=uuid.uuid4(),
        email="tx.user@acme.com",
        password_hash="hash",
        full_name="Tx User",
        is_active=True,
    )
    upload = Upload(
        id=uuid.uuid4(),
        organization_id=org.id,
        filename="stmt.csv",
        upload_type=UploadType.STATEMENT,
        storage_path="uploads/stmt.csv",
        status=UploadStatus.VALID,
    )
    db_session.add_all([org, user, upload])
    await db_session.flush()

    membership = Membership(
        id=uuid.uuid4(),
        organization_id=org.id,
        user_id=user.id,
        role=MembershipRole.ANALYST,
    )
    db_session.add(membership)

    # Seed 5 transactions with varying amounts and descriptions
    txs = []
    for i in range(1, 6):
        txs.append(
            Transaction(
                id=uuid.uuid4(),
                organization_id=org.id,
                upload_id=upload.id,
                source=TransactionSource.STATEMENT,
                transaction_date=datetime.now(timezone.utc),
                description=f"Vendor Payment {i}" if i % 2 == 0 else f"Client Deposit {i}",
                amount=Decimal(f"{i * 1000}.0000"),
                currency="USD",
                external_reference=f"REF-{1000 + i}",
                status=TransactionStatus.MATCHED if i <= 3 else TransactionStatus.EXCEPTION,
                raw_data={"row": i},
            )
        )
    db_session.add_all(txs)
    await db_session.commit()

    token = create_access_token(user_id=user.id)
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Organization-Id": str(org.id),
    }

    # 1. Test Pagination: page=1, page_size=2
    res_page = await async_client.get(
        "/api/v1/transactions?page=1&page_size=2",
        headers=headers,
    )
    assert res_page.status_code == 200
    page_data = res_page.json()
    assert page_data["total"] == 5
    assert page_data["page"] == 1
    assert page_data["page_size"] == 2
    assert page_data["total_pages"] == 3
    assert page_data["has_next"] is True
    assert len(page_data["items"]) == 2
    assert len(page_data["transactions"]) == 2

    # 2. Test Search by Description
    res_search = await async_client.get(
        "/api/v1/transactions?search=Vendor",
        headers=headers,
    )
    assert res_search.status_code == 200
    search_data = res_search.json()
    assert search_data["total"] == 2
    assert all("Vendor" in item["description"] for item in search_data["items"])

    # 3. Test Filter by Status
    res_filter = await async_client.get(
        "/api/v1/transactions?status=exception",
        headers=headers,
    )
    assert res_filter.status_code == 200
    filter_data = res_filter.json()
    assert filter_data["total"] == 2
    assert all(item["status"] == "exception" for item in filter_data["items"])

    # 4. Test Safe Sorting by amount asc
    res_sort = await async_client.get(
        "/api/v1/transactions?sort_by=amount&sort_order=asc",
        headers=headers,
    )
    assert res_sort.status_code == 200
    sort_data = res_sort.json()
    amounts = [float(item["amount"]) for item in sort_data["items"]]
    assert amounts == sorted(amounts)


@pytest.mark.asyncio
async def test_domain_foundation_routers(async_client: AsyncClient, db_session: AsyncSession):
    """Verify all domain router foundations respond with correct status and models."""
    org = Organization(id=uuid.uuid4(), name="Foundation Org", slug="found-org")
    user = User(
        id=uuid.uuid4(),
        email="found.user@acme.com",
        password_hash="hash",
        full_name="Found User",
        is_active=True,
    )
    db_session.add_all([org, user])
    await db_session.flush()

    m = Membership(
        id=uuid.uuid4(),
        organization_id=org.id,
        user_id=user.id,
        role=MembershipRole.ADMIN,
    )
    db_session.add(m)
    await db_session.commit()

    token = create_access_token(user_id=user.id)
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Organization-Id": str(org.id),
    }

    # 1. Forecast
    fc_res = await async_client.get("/api/v1/forecast?horizon=30d", headers=headers)
    assert fc_res.status_code == 200
    assert fc_res.json()["horizon"] == "30d"

    # 2. Ask
    ask_res = await async_client.post(
        "/api/v1/ask",
        headers=headers,
        json={"question": "What is the total cash balance?"},
    )
    assert ask_res.status_code == 200
    assert "answer" in ask_res.json()

    # 3. Audit
    audit_res = await async_client.get("/api/v1/audit", headers=headers)
    assert audit_res.status_code == 200
    assert "entries" in audit_res.json()

    # 4. Insights
    insights_res = await async_client.get("/api/v1/insights", headers=headers)
    assert insights_res.status_code == 200
    assert "insights" in insights_res.json()

    # 5. Exceptions list
    exc_res = await async_client.get("/api/v1/exceptions", headers=headers)
    assert exc_res.status_code == 200
    assert "exceptions" in exc_res.json()

    # Seed valid uploads for reconciliation trigger
    u_stmt = Upload(
        id=uuid.uuid4(),
        organization_id=org.id,
        filename="stmt.csv",
        upload_type=UploadType.STATEMENT,
        storage_path="uploads/stmt.csv",
        status=UploadStatus.VALID,
    )
    u_ledg = Upload(
        id=uuid.uuid4(),
        organization_id=org.id,
        filename="ledg.csv",
        upload_type=UploadType.LEDGER,
        storage_path="uploads/ledg.csv",
        status=UploadStatus.VALID,
    )
    db_session.add_all([u_stmt, u_ledg])
    await db_session.commit()

    # 6. Reconcile Trigger
    rec_res = await async_client.post(
        "/api/v1/reconcile/run",
        headers=headers,
        json={
            "statement_upload_id": str(u_stmt.id),
            "ledger_upload_id": str(u_ledg.id),
        },
    )
    assert rec_res.status_code == 201
    assert "run_id" in rec_res.json()
