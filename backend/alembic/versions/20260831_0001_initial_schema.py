"""Initial database schema migration for Ledger Control

Revision ID: 20260831_0001
Revises: 
Create Date: 2026-08-31 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260831_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create Organizations table
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_organizations")),
        sa.UniqueConstraint("slug", name=op.f("uq_organizations_slug")),
    )
    op.create_index(op.f("ix_organizations_slug"), "organizations", ["slug"], unique=True)
    op.create_index("ix_organizations_slug_trgm", "organizations", ["slug"])

    # 2. Create Users table
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index("ix_users_email_lower", "users", ["email"])

    # 3. Create Memberships table
    membership_role = sa.Enum("admin", "analyst", "viewer", name="membership_role")
    membership_role.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", membership_role, nullable=False, default="analyst"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], name=op.f("fk_memberships_organization_id_organizations"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_memberships_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_memberships")),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_memberships_org_user"),
    )
    op.create_index(op.f("ix_memberships_organization_id"), "memberships", ["organization_id"], unique=False)
    op.create_index(op.f("ix_memberships_user_id"), "memberships", ["user_id"], unique=False)
    op.create_index("ix_memberships_org_role", "memberships", ["organization_id", "role"])

    # 4. Create Uploads table
    upload_type = sa.Enum("statement", "ledger", name="upload_type")
    upload_type.create(op.get_bind(), checkfirst=True)

    upload_status = sa.Enum(
        "pending", "uploaded", "validating", "valid", "invalid", "processing", "failed",
        name="upload_status"
    )
    upload_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "uploads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("upload_type", upload_type, nullable=False),
        sa.Column("storage_path", sa.String(length=500), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("status", upload_status, nullable=False, default="pending"),
        sa.Column("validation_errors", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], name=op.f("fk_uploads_organization_id_organizations"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by"], ["users.id"], name=op.f("fk_uploads_uploaded_by_users"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_uploads")),
    )
    op.create_index(op.f("ix_uploads_organization_id"), "uploads", ["organization_id"], unique=False)
    op.create_index(op.f("ix_uploads_uploaded_by"), "uploads", ["uploaded_by"], unique=False)
    op.create_index("ix_uploads_org_status", "uploads", ["organization_id", "status"])
    op.create_index("ix_uploads_org_type", "uploads", ["organization_id", "upload_type"])

    # 5. Create ReconciliationRuns table
    reconciliation_status = sa.Enum("pending", "processing", "complete", "failed", name="reconciliation_status")
    reconciliation_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "reconciliation_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("statement_upload_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("ledger_upload_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", reconciliation_status, nullable=False, default="pending"),
        sa.Column("total_transactions", sa.Integer(), nullable=False, default=0),
        sa.Column("matched_count", sa.Integer(), nullable=False, default=0),
        sa.Column("exception_count", sa.Integer(), nullable=False, default=0),
        sa.Column("pending_review_count", sa.Integer(), nullable=False, default=0),
        sa.Column("total_value_reconciled", sa.Numeric(precision=18, scale=2), nullable=False, default=0.00),
        sa.Column("average_confidence", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], name=op.f("fk_reconciliation_runs_organization_id_organizations"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["statement_upload_id"], ["uploads.id"], name=op.f("fk_reconciliation_runs_statement_upload_id_uploads"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["ledger_upload_id"], ["uploads.id"], name=op.f("fk_reconciliation_runs_ledger_upload_id_uploads"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_reconciliation_runs_created_by_users"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reconciliation_runs")),
    )
    op.create_index(op.f("ix_reconciliation_runs_organization_id"), "reconciliation_runs", ["organization_id"], unique=False)
    op.create_index(op.f("ix_reconciliation_runs_status"), "reconciliation_runs", ["status"], unique=False)
    op.create_index("ix_reconciliation_runs_org_status", "reconciliation_runs", ["organization_id", "status"])
    op.create_index("ix_reconciliation_runs_id_status", "reconciliation_runs", ["id", "status"])

    # 6. Create Transactions table
    transaction_source = sa.Enum("statement", "ledger", name="transaction_source")
    transaction_source.create(op.get_bind(), checkfirst=True)

    transaction_status = sa.Enum("matched", "exception", "pending_review", name="transaction_status")
    transaction_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reconciliation_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("upload_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source", transaction_source, nullable=False),
        sa.Column("transaction_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("normalized_description", sa.Text(), nullable=True),
        sa.Column("amount", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, default="USD"),
        sa.Column("external_reference", sa.String(length=255), nullable=True),
        sa.Column("normalized_reference", sa.String(length=255), nullable=True),
        sa.Column("normalized_hash", sa.String(length=64), nullable=True),
        sa.Column("status", transaction_status, nullable=False, default="pending_review"),
        sa.Column("confidence", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("raw_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], name=op.f("fk_transactions_organization_id_organizations"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["reconciliation_run_id"], ["reconciliation_runs.id"], name=op.f("fk_transactions_reconciliation_run_id_reconciliation_runs"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["upload_id"], ["uploads.id"], name=op.f("fk_transactions_upload_id_uploads"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_transactions")),
    )
    op.create_index(op.f("ix_transactions_organization_id"), "transactions", ["organization_id"], unique=False)
    op.create_index(op.f("ix_transactions_reconciliation_run_id"), "transactions", ["reconciliation_run_id"], unique=False)
    op.create_index(op.f("ix_transactions_upload_id"), "transactions", ["upload_id"], unique=False)
    op.create_index(op.f("ix_transactions_status"), "transactions", ["status"], unique=False)
    op.create_index(op.f("ix_transactions_transaction_date"), "transactions", ["transaction_date"], unique=False)
    op.create_index(op.f("ix_transactions_external_reference"), "transactions", ["external_reference"], unique=False)
    op.create_index(op.f("ix_transactions_normalized_hash"), "transactions", ["normalized_hash"], unique=False)
    op.create_index("ix_transactions_org_status", "transactions", ["organization_id", "status"])
    op.create_index("ix_transactions_org_run", "transactions", ["organization_id", "reconciliation_run_id"])
    op.create_index("ix_transactions_org_date", "transactions", ["organization_id", "transaction_date"])
    op.create_index("ix_transactions_org_hash", "transactions", ["organization_id", "normalized_hash"])

    # 7. Create Matches table
    match_method = sa.Enum("deterministic", "fuzzy", "manual", name="match_method")
    match_method.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "matches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reconciliation_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("statement_transaction_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ledger_transaction_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("method", match_method, nullable=False),
        sa.Column("confidence", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("score_details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], name=op.f("fk_matches_organization_id_organizations"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["reconciliation_run_id"], ["reconciliation_runs.id"], name=op.f("fk_matches_reconciliation_run_id_reconciliation_runs"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["statement_transaction_id"], ["transactions.id"], name=op.f("fk_matches_statement_transaction_id_transactions"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["ledger_transaction_id"], ["transactions.id"], name=op.f("fk_matches_ledger_transaction_id_transactions"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_matches")),
    )
    op.create_index(op.f("ix_matches_organization_id"), "matches", ["organization_id"], unique=False)
    op.create_index(op.f("ix_matches_reconciliation_run_id"), "matches", ["reconciliation_run_id"], unique=False)
    op.create_index("ix_matches_org_run", "matches", ["organization_id", "reconciliation_run_id"])
    op.create_index("ix_matches_statement_tx", "matches", ["statement_transaction_id"])
    op.create_index("ix_matches_ledger_tx", "matches", ["ledger_transaction_id"])

    # 8. Create Exceptions table
    exception_priority = sa.Enum("low", "medium", "high", "critical", name="exception_priority")
    exception_priority.create(op.get_bind(), checkfirst=True)

    exception_status = sa.Enum("open", "reviewing", "resolved", "rejected", name="exception_status")
    exception_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "exceptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reconciliation_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("transaction_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("best_candidate_transaction_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reason_text", sa.Text(), nullable=False),
        sa.Column("priority", exception_priority, nullable=False, default="medium"),
        sa.Column("status", exception_status, nullable=False, default="open"),
        sa.Column("resolution_action", sa.String(length=255), nullable=True),
        sa.Column("resolved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], name=op.f("fk_exceptions_organization_id_organizations"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["reconciliation_run_id"], ["reconciliation_runs.id"], name=op.f("fk_exceptions_reconciliation_run_id_reconciliation_runs"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["transaction_id"], ["transactions.id"], name=op.f("fk_exceptions_transaction_id_transactions"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["best_candidate_transaction_id"], ["transactions.id"], name=op.f("fk_exceptions_best_candidate_transaction_id_transactions"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["resolved_by"], ["users.id"], name=op.f("fk_exceptions_resolved_by_users"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_exceptions")),
    )
    op.create_index(op.f("ix_exceptions_organization_id"), "exceptions", ["organization_id"], unique=False)
    op.create_index(op.f("ix_exceptions_reconciliation_run_id"), "exceptions", ["reconciliation_run_id"], unique=False)
    op.create_index(op.f("ix_exceptions_transaction_id"), "exceptions", ["transaction_id"], unique=False)
    op.create_index(op.f("ix_exceptions_priority"), "exceptions", ["priority"], unique=False)
    op.create_index(op.f("ix_exceptions_status"), "exceptions", ["status"], unique=False)
    op.create_index("ix_exceptions_org_status_priority", "exceptions", ["organization_id", "status", "priority"])
    op.create_index("ix_exceptions_org_run", "exceptions", ["organization_id", "reconciliation_run_id"])

    # 9. Create AuditLogs table
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], name=op.f("fk_audit_logs_organization_id_organizations"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["users.id"], name=op.f("fk_audit_logs_actor_id_users"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_logs")),
    )
    op.create_index(op.f("ix_audit_logs_organization_id"), "audit_logs", ["organization_id"], unique=False)
    op.create_index(op.f("ix_audit_logs_created_at"), "audit_logs", ["created_at"], unique=False)
    op.create_index("ix_audit_logs_org_created_at", "audit_logs", ["organization_id", "created_at"])
    op.create_index("ix_audit_logs_entity", "audit_logs", ["entity_type", "entity_id"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("exceptions")
    op.drop_table("matches")
    op.drop_table("transactions")
    op.drop_table("reconciliation_runs")
    op.drop_table("uploads")
    op.drop_table("memberships")
    op.drop_table("users")
    op.drop_table("organizations")

    # Drop Enums
    sa.Enum(name="exception_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="exception_priority").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="match_method").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="transaction_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="transaction_source").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="reconciliation_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="upload_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="upload_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="membership_role").drop(op.get_bind(), checkfirst=True)
