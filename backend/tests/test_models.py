import uuid
from decimal import Decimal
from datetime import datetime, timezone
import pytest
from sqlalchemy import Numeric
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.db.base import Base
from app.models import (
    AuditLog,
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


def test_metadata_contains_all_tables():
    """Verify that all 9 required domain entities are registered in SQLAlchemy metadata."""
    expected_tables = {
        "organizations",
        "users",
        "memberships",
        "uploads",
        "reconciliation_runs",
        "transactions",
        "matches",
        "exceptions",
        "audit_logs",
    }
    actual_tables = set(Base.metadata.tables.keys())
    assert expected_tables.issubset(actual_tables), f"Missing tables: {expected_tables - actual_tables}"


def test_uuid_primary_keys():
    """Ensure all entity primary keys are configured as UUID types."""
    for table_name, table in Base.metadata.tables.items():
        pk_columns = [col for col in table.columns if col.primary_key]
        assert len(pk_columns) == 1, f"Table {table_name} must have exactly one primary key column"
        pk_col = pk_columns[0]
        assert isinstance(pk_col.type, UUID), f"Table {table_name} PK column {pk_col.name} must be UUID"


def test_numeric_for_financial_values():
    """Ensure financial columns strictly use Numeric/Decimal precision and never Float."""
    tx_table = Base.metadata.tables["transactions"]
    amount_col = tx_table.columns["amount"]
    assert isinstance(amount_col.type, Numeric), "Transaction amount must be Numeric"
    assert amount_col.type.precision == 18
    assert amount_col.type.scale == 4

    run_table = Base.metadata.tables["reconciliation_runs"]
    reconciled_col = run_table.columns["total_value_reconciled"]
    assert isinstance(reconciled_col.type, Numeric), "Total value reconciled must be Numeric"
    assert reconciled_col.type.precision == 18
    assert reconciled_col.type.scale == 2


def test_jsonb_columns_present():
    """Ensure structured/raw data columns use PostgreSQL JSONB."""
    tx_table = Base.metadata.tables["transactions"]
    assert isinstance(tx_table.columns["raw_data"].type, JSONB)

    upload_table = Base.metadata.tables["uploads"]
    assert isinstance(upload_table.columns["validation_errors"].type, JSONB)

    match_table = Base.metadata.tables["matches"]
    assert isinstance(match_table.columns["score_details"].type, JSONB)

    audit_table = Base.metadata.tables["audit_logs"]
    assert isinstance(audit_table.columns["details"].type, JSONB)


def test_model_instantiation():
    """Verify instantiating models works as expected with UUIDs, Numeric decimals, and enums."""
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    upload_id = uuid.uuid4()
    run_id = uuid.uuid4()
    tx1_id = uuid.uuid4()
    tx2_id = uuid.uuid4()

    org = Organization(id=org_id, name="Acme Corp", slug="acme-corp")
    assert org.id == org_id
    assert org.slug == "acme-corp"

    user = User(
        id=user_id,
        email="finance@acme.com",
        password_hash="argon2_placeholder",
        full_name="Jane Doe",
        is_active=True,
    )
    assert user.id == user_id
    assert user.is_active is True

    # Test column default definition for is_active
    user_table = Base.metadata.tables["users"]
    assert user_table.columns["is_active"].default.arg is True

    membership = Membership(
        organization_id=org_id,
        user_id=user_id,
        role=MembershipRole.ADMIN,
    )
    assert membership.role == MembershipRole.ADMIN
    assert membership.organization_id == org_id

    upload = Upload(
        id=upload_id,
        organization_id=org_id,
        filename="bank_statement_aug2026.csv",
        upload_type=UploadType.STATEMENT,
        storage_path="uploads/org_1/bank_statement_aug2026.csv",
        status=UploadStatus.UPLOADED,
        row_count=150,
    )
    assert upload.upload_type == UploadType.STATEMENT
    assert upload.status == UploadStatus.UPLOADED

    run = ReconciliationRun(
        id=run_id,
        organization_id=org_id,
        statement_upload_id=upload_id,
        status=ReconciliationStatus.PROCESSING,
        total_transactions=100,
        matched_count=80,
        exception_count=20,
        pending_review_count=10,
        total_value_reconciled=Decimal("254300.50"),
        average_confidence=Decimal("0.9850"),
    )
    assert run.total_value_reconciled == Decimal("254300.50")
    assert run.average_confidence == Decimal("0.9850")

    tx1 = Transaction(
        id=tx1_id,
        organization_id=org_id,
        reconciliation_run_id=run_id,
        upload_id=upload_id,
        source=TransactionSource.STATEMENT,
        transaction_date=datetime.now(timezone.utc),
        description="Payment Received from ACME Client",
        amount=Decimal("15250.7500"),
        currency="USD",
        status=TransactionStatus.MATCHED,
        confidence=Decimal("0.9950"),
        raw_data={"raw_id": "STMT_001", "channel": "WIRE"},
    )
    assert tx1.amount == Decimal("15250.7500")
    assert tx1.currency == "USD"
    assert tx1.confidence == Decimal("0.9950")

    tx2 = Transaction(
        id=tx2_id,
        organization_id=org_id,
        reconciliation_run_id=run_id,
        upload_id=upload_id,
        source=TransactionSource.LEDGER,
        transaction_date=datetime.now(timezone.utc),
        description="GL 1010 - Client Invoice Payment",
        amount=Decimal("15250.7500"),
        currency="USD",
        status=TransactionStatus.MATCHED,
        confidence=Decimal("0.9950"),
        raw_data={"gl_account": "1010-00", "journal_id": "JV-9901"},
    )

    match = Match(
        organization_id=org_id,
        reconciliation_run_id=run_id,
        statement_transaction_id=tx1_id,
        ledger_transaction_id=tx2_id,
        method=MatchMethod.DETERMINISTIC,
        confidence=Decimal("1.0000"),
        score_details={"exact_amount": True, "date_delta_days": 0, "ref_match": True},
    )
    assert match.method == MatchMethod.DETERMINISTIC
    assert match.confidence == Decimal("1.0000")

    exc = ReconciliationException(
        organization_id=org_id,
        reconciliation_run_id=run_id,
        transaction_id=tx1_id,
        reason_text="Unmatched transaction amount discrepancy",
        priority=ExceptionPriority.HIGH,
        status=ExceptionStatus.OPEN,
    )
    assert exc.priority == ExceptionPriority.HIGH
    assert exc.status == ExceptionStatus.OPEN

    audit = AuditLog(
        organization_id=org_id,
        actor_id=user_id,
        action="reconciliation.run_created",
        entity_type="ReconciliationRun",
        entity_id=run_id,
        details={"initiated_by": "manual"},
        ip_address="127.0.0.1",
    )
    assert audit.action == "reconciliation.run_created"
    assert audit.details == {"initiated_by": "manual"}
