import io
import uuid
from decimal import Decimal
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import create_access_token
from app.models import Membership, MembershipRole, Organization, Transaction, TransactionSource, Upload, UploadStatus, UploadType, User


@pytest.mark.asyncio
async def test_statement_upload_success(async_client: AsyncClient, db_session: AsyncSession):
    """Test standard Statement CSV upload with Date, Description, Amount, and Reference."""
    org = Organization(id=uuid.uuid4(), name="Upload Org", slug="upload-org")
    user = User(
        id=uuid.uuid4(),
        email="uploader@acme.com",
        password_hash="hash",
        full_name="Uploader User",
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
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Organization-Id": str(org.id),
    }

    csv_content = (
        "Date,Description,Amount,Reference,Currency\n"
        "2026-08-01,Stripe Payout Ref 1001,15420.50,TXN-1001,USD\n"
        "2026-08-02,AWS Cloud Hosting,(450.25),INV-9921,USD\n"
        "2026-08-03,Client Invoice Wire,2500.00,WIRE-881,USD\n"
    )

    files = {"file": ("statement_aug.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}

    response = await async_client.post("/api/v1/uploads/statement", headers=headers, files=files)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "valid"
    assert data["rows"] == 3
    assert data["upload_type"] == "statement"
    assert "upload_id" in data

    upload_id = uuid.UUID(data["upload_id"])

    # Verify transactions created in DB
    stmt = select(Transaction).where(Transaction.upload_id == upload_id).order_by(Transaction.amount.desc())
    result = await db_session.execute(stmt)
    txs = result.scalars().all()
    assert len(txs) == 3

    # Check first transaction
    tx_stripe = next(t for t in txs if "Stripe" in t.description)
    assert tx_stripe.amount == Decimal("15420.5000")
    assert tx_stripe.normalized_description == "stripe payout ref 1001"
    assert tx_stripe.normalized_reference == "TXN-1001"
    assert tx_stripe.source == TransactionSource.STATEMENT
    assert tx_stripe.normalized_hash is not None

    # Check negative amount transaction (parentheses format)
    tx_aws = next(t for t in txs if "AWS" in t.description)
    assert tx_aws.amount == Decimal("-450.2500")


@pytest.mark.asyncio
async def test_ledger_upload_with_debit_credit_columns(async_client: AsyncClient, db_session: AsyncSession):
    """Test Ledger CSV with separate Debit and Credit columns."""
    org = Organization(id=uuid.uuid4(), name="Ledger Org", slug="ledger-org")
    user = User(id=uuid.uuid4(), email="ledger.user@acme.com", password_hash="hash", full_name="Ledger User", is_active=True)
    db_session.add_all([org, user])
    await db_session.flush()

    m = Membership(id=uuid.uuid4(), organization_id=org.id, user_id=user.id, role=MembershipRole.ANALYST)
    db_session.add(m)
    await db_session.commit()

    token = create_access_token(user_id=user.id)
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": str(org.id)}

    csv_content = (
        "Posting Date,Account Memo,Debit,Credit,Journal ID\n"
        "08/01/2026,Accounts Receivable Client Payment,0.00,15420.50,JV-1001\n"
        "08/02/2026,Office Supplies Vendor,120.00,0.00,JV-1002\n"
    )

    files = {"file": ("general_ledger.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}

    response = await async_client.post("/api/v1/uploads/ledger", headers=headers, files=files)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "valid"
    assert data["rows"] == 2
    assert data["upload_type"] == "ledger"

    upload_id = uuid.UUID(data["upload_id"])
    stmt = select(Transaction).where(Transaction.upload_id == upload_id)
    result = await db_session.execute(stmt)
    txs = result.scalars().all()

    tx_ar = next(t for t in txs if "Receivable" in t.description)
    assert tx_ar.amount == Decimal("15420.5000")  # Credit is positive inflow

    tx_supplies = next(t for t in txs if "Supplies" in t.description)
    assert tx_supplies.amount == Decimal("-120.0000")  # Debit is negative outflow


@pytest.mark.asyncio
async def test_missing_required_headers_handling(async_client: AsyncClient, db_session: AsyncSession):
    """Test file with invalid/missing headers is marked invalid without crashing."""
    org = Organization(id=uuid.uuid4(), name="Invalid Org", slug="invalid-org")
    user = User(id=uuid.uuid4(), email="invalid.user@acme.com", password_hash="hash", full_name="Invalid User", is_active=True)
    db_session.add_all([org, user])
    await db_session.flush()

    m = Membership(id=uuid.uuid4(), organization_id=org.id, user_id=user.id, role=MembershipRole.ANALYST)
    db_session.add(m)
    await db_session.commit()

    token = create_access_token(user_id=user.id)
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": str(org.id)}

    csv_content = (
        "RandomColA,RandomColB,Notes\n"
        "val1,val2,val3\n"
    )

    files = {"file": ("bad_headers.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}

    response = await async_client.post("/api/v1/uploads/statement", headers=headers, files=files)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "invalid"
    assert data["rows"] == 0
    assert data["validation_errors"] is not None
    assert "header_errors" in data["validation_errors"]


@pytest.mark.asyncio
async def test_partial_row_errors_reporting(async_client: AsyncClient, db_session: AsyncSession):
    """Test CSV containing a malformed amount row ingests valid rows while capturing the error."""
    org = Organization(id=uuid.uuid4(), name="Partial Org", slug="partial-org")
    user = User(id=uuid.uuid4(), email="partial.user@acme.com", password_hash="hash", full_name="Partial User", is_active=True)
    db_session.add_all([org, user])
    await db_session.flush()

    m = Membership(id=uuid.uuid4(), organization_id=org.id, user_id=user.id, role=MembershipRole.ANALYST)
    db_session.add(m)
    await db_session.commit()

    token = create_access_token(user_id=user.id)
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": str(org.id)}

    csv_content = (
        "Date,Description,Amount\n"
        "2026-08-01,Valid Row One,100.00\n"
        "2026-08-02,Malformed Amount Row,CORRUPT_AMOUNT\n"
        "2026-08-03,Valid Row Three,300.00\n"
    )

    files = {"file": ("partial.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}

    response = await async_client.post("/api/v1/uploads/statement", headers=headers, files=files)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "valid"
    assert data["rows"] == 2
    assert data["validation_errors"] is not None
    assert data["validation_errors"]["invalid_rows_count"] == 1


@pytest.mark.asyncio
async def test_duplicate_detection_flagging(async_client: AsyncClient, db_session: AsyncSession):
    """Test that uploading duplicate records flags them in raw_data rather than deleting them."""
    org = Organization(id=uuid.uuid4(), name="Dupe Org", slug="dupe-org")
    user = User(id=uuid.uuid4(), email="dupe.user@acme.com", password_hash="hash", full_name="Dupe User", is_active=True)
    db_session.add_all([org, user])
    await db_session.flush()

    m = Membership(id=uuid.uuid4(), organization_id=org.id, user_id=user.id, role=MembershipRole.ANALYST)
    db_session.add(m)
    await db_session.commit()

    token = create_access_token(user_id=user.id)
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": str(org.id)}

    csv_content = (
        "Date,Description,Amount,Reference\n"
        "2026-08-10,Exact Duplicate Transaction,500.00,REF-999\n"
    )

    # 1. First Upload
    files1 = {"file": ("first_upload.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    res1 = await async_client.post("/api/v1/uploads/statement", headers=headers, files=files1)
    assert res1.status_code == 201
    upload_1_id = uuid.UUID(res1.json()["upload_id"])

    # 2. Second Upload with identical record
    files2 = {"file": ("second_upload.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    res2 = await async_client.post("/api/v1/uploads/statement", headers=headers, files=files2)
    assert res2.status_code == 201
    upload_2_id = uuid.UUID(res2.json()["upload_id"])

    # Check second upload transaction flagged as duplicate
    stmt = select(Transaction).where(Transaction.upload_id == upload_2_id)
    result = await db_session.execute(stmt)
    tx2 = result.scalar_one()
    assert tx2.raw_data["_is_duplicate"] is True


@pytest.mark.asyncio
async def test_cross_tenant_upload_blocked(async_client: AsyncClient, db_session: AsyncSession):
    """Ensure user cannot upload to an organization they do not belong to."""
    org1 = Organization(id=uuid.uuid4(), name="Org 1", slug="org-1-upload")
    org2 = Organization(id=uuid.uuid4(), name="Org 2", slug="org-2-upload")
    user = User(id=uuid.uuid4(), email="tenant.uploader@acme.com", password_hash="hash", full_name="Tenant Uploader", is_active=True)

    db_session.add_all([org1, org2, user])
    await db_session.flush()

    m1 = Membership(id=uuid.uuid4(), organization_id=org1.id, user_id=user.id, role=MembershipRole.ANALYST)
    db_session.add(m1)
    await db_session.commit()

    token = create_access_token(user_id=user.id)

    csv_content = "Date,Description,Amount\n2026-08-01,Payment,100.00\n"
    files = {"file": ("test.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}

    # Attempt to upload to Org 2 (User is not a member)
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": str(org2.id)}
    res = await async_client.post("/api/v1/uploads/statement", headers=headers, files=files)
    assert res.status_code == 403
