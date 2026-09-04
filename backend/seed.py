"""
Seed Script for Ledger Control Local Development
Creates all tables, a default demo organization, demo admin account, and sample data.
"""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles

from app.core.database import async_session_factory, engine
from app.core.security import hash_password
from app.db.base import Base


@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"
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


async def seed():
    print("[+] Initializing database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as db:
        # Check if demo user exists
        stmt = select(User).where(User.email == "admin@ledgercontrol.com")
        res = await db.execute(stmt)
        existing_user = res.scalar_one_or_none()

        if existing_user:
            print("[i] Demo user admin@ledgercontrol.com already exists.")
            return

        print("[+] Creating demo Organization and User...")
        org = Organization(
            id=uuid.uuid4(),
            name="Acme Financial Corp",
            slug="acme-financial",
        )
        user = User(
            id=uuid.uuid4(),
            email="admin@ledgercontrol.com",
            password_hash=hash_password("Password123!"),
            full_name="Alex Mercer (Admin)",
            is_active=True,
        )
        db.add_all([org, user])
        await db.flush()

        membership = Membership(
            id=uuid.uuid4(),
            organization_id=org.id,
            user_id=user.id,
            role=MembershipRole.ADMIN,
        )
        db.add(membership)

        # Create Uploads
        upload_stmt = Upload(
            id=uuid.uuid4(),
            organization_id=org.id,
            filename="bank_statement_aug2026.csv",
            upload_type=UploadType.STATEMENT,
            storage_path="storage/uploads/bank_statement_aug2026.csv",
            row_count=5,
            status=UploadStatus.VALID,
        )
        upload_ledg = Upload(
            id=uuid.uuid4(),
            organization_id=org.id,
            filename="gateway_ledger_aug2026.csv",
            upload_type=UploadType.LEDGER,
            storage_path="storage/uploads/gateway_ledger_aug2026.csv",
            row_count=5,
            status=UploadStatus.VALID,
        )
        db.add_all([upload_stmt, upload_ledg])
        await db.flush()

        # Create Reconciliation Run
        run = ReconciliationRun(
            id=uuid.uuid4(),
            organization_id=org.id,
            statement_upload_id=upload_stmt.id,
            ledger_upload_id=upload_ledg.id,
            status=ReconciliationStatus.COMPLETE,
            total_transactions=6,
            matched_count=4,
            exception_count=2,
            pending_review_count=0,
            total_value_reconciled=Decimal("18500.00"),
            average_confidence=Decimal("0.9650"),
            created_by=user.id,
            started_at=datetime.now(timezone.utc) - timedelta(minutes=15),
            completed_at=datetime.now(timezone.utc) - timedelta(minutes=14),
        )
        db.add(run)
        await db.flush()

        # Create Transactions & Matches
        base_dt = datetime(2026, 8, 15, 10, 0, tzinfo=timezone.utc)
        
        # Matched 1: Stripe payout
        s1 = Transaction(
            id=uuid.uuid4(), organization_id=org.id, upload_id=upload_stmt.id,
            reconciliation_run_id=run.id, source=TransactionSource.STATEMENT,
            transaction_date=base_dt, description="STRIPE PAYOUT #9901",
            normalized_description="stripe payout 9901", amount=Decimal("12500.00"),
            currency="USD", external_reference="STRIPE-9901", normalized_reference="STRIPE-9901",
            status=TransactionStatus.MATCHED, confidence=Decimal("1.0000"), raw_data={},
        )
        l1 = Transaction(
            id=uuid.uuid4(), organization_id=org.id, upload_id=upload_ledg.id,
            reconciliation_run_id=run.id, source=TransactionSource.LEDGER,
            transaction_date=base_dt, description="Stripe Deposit Payout",
            normalized_description="stripe deposit payout", amount=Decimal("12500.00"),
            currency="USD", external_reference="STRIPE-9901", normalized_reference="STRIPE-9901",
            status=TransactionStatus.MATCHED, confidence=Decimal("1.0000"), raw_data={},
        )
        db.add_all([s1, l1])
        await db.flush()
        
        m1 = Match(
            id=uuid.uuid4(), organization_id=org.id, reconciliation_run_id=run.id,
            statement_transaction_id=s1.id, ledger_transaction_id=l1.id,
            method=MatchMethod.DETERMINISTIC, confidence=Decimal("1.0000"),
            score_details={"rule": "Rule 1: Exact Reference Match"},
        )
        db.add(m1)

        # Matched 2: AWS Cloud
        s2 = Transaction(
            id=uuid.uuid4(), organization_id=org.id, upload_id=upload_stmt.id,
            reconciliation_run_id=run.id, source=TransactionSource.STATEMENT,
            transaction_date=base_dt + timedelta(days=1), description="AWS EMEA INVOICE",
            normalized_description="aws emea invoice", amount=Decimal("6000.00"),
            currency="USD", external_reference="INV-AWS-882", normalized_reference="INV-AWS-882",
            status=TransactionStatus.MATCHED, confidence=Decimal("0.9800"), raw_data={},
        )
        l2 = Transaction(
            id=uuid.uuid4(), organization_id=org.id, upload_id=upload_ledg.id,
            reconciliation_run_id=run.id, source=TransactionSource.LEDGER,
            transaction_date=base_dt + timedelta(days=1), description="Amazon Web Services EMEA",
            normalized_description="amazon web services emea", amount=Decimal("6000.00"),
            currency="USD", external_reference="INV-AWS-882", normalized_reference="INV-AWS-882",
            status=TransactionStatus.MATCHED, confidence=Decimal("0.9800"), raw_data={},
        )
        db.add_all([s2, l2])
        await db.flush()

        m2 = Match(
            id=uuid.uuid4(), organization_id=org.id, reconciliation_run_id=run.id,
            statement_transaction_id=s2.id, ledger_transaction_id=l2.id,
            method=MatchMethod.FUZZY, confidence=Decimal("0.9800"),
            score_details={"rule": "Fuzzy token similarity 98%"},
        )
        db.add(m2)

        # Exception 1: Unmatched Bank Wire
        s3 = Transaction(
            id=uuid.uuid4(), organization_id=org.id, upload_id=upload_stmt.id,
            reconciliation_run_id=run.id, source=TransactionSource.STATEMENT,
            transaction_date=base_dt + timedelta(days=2), description="UNKNOWN WIRE INFLOW",
            normalized_description="unknown wire inflow", amount=Decimal("4500.00"),
            currency="USD", status=TransactionStatus.EXCEPTION, raw_data={},
        )
        # Potential candidate on ledger side
        l3 = Transaction(
            id=uuid.uuid4(), organization_id=org.id, upload_id=upload_ledg.id,
            reconciliation_run_id=run.id, source=TransactionSource.LEDGER,
            transaction_date=base_dt + timedelta(days=2), description="Consulting Client Wire",
            normalized_description="consulting client wire", amount=Decimal("4500.00"),
            currency="USD", status=TransactionStatus.PENDING_REVIEW, raw_data={},
        )
        db.add_all([s3, l3])
        await db.flush()

        exc1 = ReconciliationException(
            id=uuid.uuid4(), organization_id=org.id, reconciliation_run_id=run.id,
            transaction_id=s3.id, best_candidate_transaction_id=l3.id,
            reason_text="Unmatched wire inflow; candidate found with exact amount ($4,500.00) and same date.",
            priority=ExceptionPriority.HIGH, status=ExceptionStatus.OPEN,
        )
        db.add(exc1)

        # Audit Logs
        audit1 = AuditLog(
            id=uuid.uuid4(), organization_id=org.id, actor_id=user.id,
            action="auth.login", entity_type="User", entity_id=user.id,
            details={"ip_address": "127.0.0.1"},
        )
        audit2 = AuditLog(
            id=uuid.uuid4(), organization_id=org.id, actor_id=user.id,
            action="reconciliation.completed", entity_type="ReconciliationRun", entity_id=run.id,
            details={"matched_count": 4, "exception_count": 2, "total_value": "18500.00"},
        )
        db.add_all([audit1, audit2])
        await db.commit()

        print("[+] Demo data seeded successfully!")
        print("----------------------------------------------------")
        print("Login Credentials:")
        print("   Email:    admin@ledgercontrol.com")
        print("   Password: Password123!")
        print("----------------------------------------------------")


if __name__ == "__main__":
    asyncio.run(seed())
