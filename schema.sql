-- =============================================================================
-- LEDGER CONTROL — COMPLETE PRODUCTION POSTGRESQL DDL SCHEMA
-- Project: Ledger Control (AI Finance Controller)
-- Database Engine: PostgreSQL 16+
-- Encoding: UTF-8
-- Timezone: UTC
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- -----------------------------------------------------------------------------
-- 1. CUSTOM ENUM TYPES
-- -----------------------------------------------------------------------------
CREATE TYPE membership_role AS ENUM ('admin', 'analyst', 'viewer');
CREATE TYPE upload_type AS ENUM ('statement', 'ledger');
CREATE TYPE upload_status AS ENUM ('pending', 'valid', 'invalid');
CREATE TYPE reconciliation_status AS ENUM ('pending', 'processing', 'complete', 'failed');
CREATE TYPE transaction_source AS ENUM ('statement', 'ledger');
CREATE TYPE transaction_status AS ENUM ('unmatched', 'matched', 'exception', 'pending_review');
CREATE TYPE match_method AS ENUM ('deterministic', 'fuzzy', 'manual');
CREATE TYPE exception_priority AS ENUM ('low', 'medium', 'high', 'critical');
CREATE TYPE exception_status AS ENUM ('open', 'pending_review', 'resolved', 'rejected');
CREATE TYPE insight_severity AS ENUM ('low', 'medium', 'high', 'critical');
CREATE TYPE forecast_horizon AS ENUM ('7d', '30d', '90d');

-- -----------------------------------------------------------------------------
-- 2. ORGANIZATIONS (Multi-Tenant Workspace Partitioning)
-- -----------------------------------------------------------------------------
CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX ix_organizations_slug ON organizations (slug);

-- -----------------------------------------------------------------------------
-- 3. USERS
-- -----------------------------------------------------------------------------
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX ix_users_email_lower ON users (LOWER(email));

-- -----------------------------------------------------------------------------
-- 4. MEMBERSHIPS (Role-Based Access Control)
-- -----------------------------------------------------------------------------
CREATE TABLE memberships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role membership_role NOT NULL DEFAULT 'viewer',
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT uq_membership_org_user UNIQUE (organization_id, user_id)
);
CREATE INDEX ix_memberships_user_id ON memberships (user_id);
CREATE INDEX ix_memberships_org_id ON memberships (organization_id);

-- -----------------------------------------------------------------------------
-- 5. REFRESH TOKENS (Session Security & Token Rotation)
-- -----------------------------------------------------------------------------
CREATE TABLE refresh_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    token_hash VARCHAR(64) NOT NULL UNIQUE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX ix_refresh_tokens_user_id ON refresh_tokens (user_id);
CREATE INDEX ix_refresh_tokens_hash ON refresh_tokens (token_hash);

-- -----------------------------------------------------------------------------
-- 6. UPLOADS (Bank Statement and Ledger File Records)
-- -----------------------------------------------------------------------------
CREATE TABLE uploads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    upload_type upload_type NOT NULL,
    storage_path VARCHAR(1024) NOT NULL,
    row_count INTEGER DEFAULT 0,
    status upload_status NOT NULL DEFAULT 'pending',
    validation_errors JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX ix_uploads_organization_id ON uploads (organization_id);
CREATE INDEX ix_uploads_org_created ON uploads (organization_id, created_at DESC);

-- -----------------------------------------------------------------------------
-- 7. RECONCILIATION RUNS (Execution Metrics & Lifecycle)
-- -----------------------------------------------------------------------------
CREATE TABLE reconciliation_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    statement_upload_id UUID NOT NULL REFERENCES uploads(id) ON DELETE CASCADE,
    ledger_upload_id UUID REFERENCES uploads(id) ON DELETE SET NULL,
    status reconciliation_status NOT NULL DEFAULT 'pending',
    total_transactions INTEGER NOT NULL DEFAULT 0,
    matched_count INTEGER NOT NULL DEFAULT 0,
    exception_count INTEGER NOT NULL DEFAULT 0,
    pending_review_count INTEGER NOT NULL DEFAULT 0,
    total_value_reconciled NUMERIC(18, 4) NOT NULL DEFAULT 0.0000,
    average_confidence NUMERIC(5, 4),
    error_message TEXT,
    created_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX ix_reconciliation_runs_user_id ON reconciliation_runs (created_by);
CREATE INDEX ix_reconciliation_runs_org_id ON reconciliation_runs (organization_id);
CREATE INDEX ix_reconciliation_runs_status ON reconciliation_runs (status);
CREATE INDEX ix_reconciliation_runs_created ON reconciliation_runs (created_at DESC);

-- -----------------------------------------------------------------------------
-- 8. TRANSACTIONS (Financial Ledger Entries)
-- -----------------------------------------------------------------------------
CREATE TABLE transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    upload_id UUID NOT NULL REFERENCES uploads(id) ON DELETE CASCADE,
    reconciliation_run_id UUID REFERENCES reconciliation_runs(id) ON DELETE SET NULL,
    source transaction_source NOT NULL,
    transaction_date TIMESTAMPTZ NOT NULL,
    description TEXT NOT NULL,
    normalized_description TEXT,
    amount NUMERIC(18, 4) NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    external_reference VARCHAR(255),
    normalized_reference VARCHAR(255),
    status transaction_status NOT NULL DEFAULT 'unmatched',
    confidence NUMERIC(5, 4),
    transaction_hash VARCHAR(64),
    raw_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX ix_transactions_org_id ON transactions (organization_id);
CREATE INDEX ix_transactions_run_id ON transactions (reconciliation_run_id);
CREATE INDEX ix_transactions_date ON transactions (transaction_date DESC);
CREATE INDEX ix_transactions_status ON transactions (status);
CREATE INDEX ix_transactions_source ON transactions (source);
CREATE INDEX ix_transactions_external_ref ON transactions (external_reference);
CREATE INDEX ix_transactions_norm_ref ON transactions (normalized_reference);
CREATE INDEX ix_transactions_amount ON transactions (amount);

-- -----------------------------------------------------------------------------
-- 9. MATCHES (Reconciliation Match Pairs & Confidence Scorer)
-- -----------------------------------------------------------------------------
CREATE TABLE matches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    reconciliation_run_id UUID NOT NULL REFERENCES reconciliation_runs(id) ON DELETE CASCADE,
    statement_transaction_id UUID NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
    ledger_transaction_id UUID NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
    method match_method NOT NULL,
    confidence NUMERIC(5, 4) NOT NULL,
    score_details JSONB,
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT uq_matches_statement_tx UNIQUE (statement_transaction_id),
    CONSTRAINT uq_matches_ledger_tx UNIQUE (ledger_transaction_id)
);
CREATE INDEX ix_matches_org_id ON matches (organization_id);
CREATE INDEX ix_matches_run_id ON matches (reconciliation_run_id);
CREATE INDEX ix_matches_method ON matches (method);

-- -----------------------------------------------------------------------------
-- 10. EXCEPTIONS (Discrepancies & Low-Confidence Items)
-- -----------------------------------------------------------------------------
CREATE TABLE exceptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    reconciliation_run_id UUID NOT NULL REFERENCES reconciliation_runs(id) ON DELETE CASCADE,
    transaction_id UUID NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
    best_candidate_transaction_id UUID REFERENCES transactions(id) ON DELETE SET NULL,
    reason_text TEXT NOT NULL,
    priority exception_priority NOT NULL DEFAULT 'medium',
    status exception_status NOT NULL DEFAULT 'open',
    resolution_action VARCHAR(50),
    resolved_by UUID REFERENCES users(id) ON DELETE SET NULL,
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX ix_exceptions_org_id ON exceptions (organization_id);
CREATE INDEX ix_exceptions_run_id ON exceptions (reconciliation_run_id);
CREATE INDEX ix_exceptions_transaction_id ON exceptions (transaction_id);
CREATE INDEX ix_exceptions_status ON exceptions (status);
CREATE INDEX ix_exceptions_priority ON exceptions (priority);

-- -----------------------------------------------------------------------------
-- 11. EXCEPTION RESOLUTIONS (Audit Trail of Manual & Bulk Approvals)
-- -----------------------------------------------------------------------------
CREATE TABLE exception_resolutions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    exception_id UUID NOT NULL REFERENCES exceptions(id) ON DELETE CASCADE,
    reconciliation_run_id UUID REFERENCES reconciliation_runs(id) ON DELETE SET NULL,
    action VARCHAR(50) NOT NULL,
    candidate_transaction_id UUID REFERENCES transactions(id) ON DELETE SET NULL,
    note TEXT,
    resolved_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX ix_exception_resolutions_exception_id ON exception_resolutions (exception_id);
CREATE INDEX ix_exception_resolutions_user_id ON exception_resolutions (resolved_by);
CREATE INDEX ix_exception_resolutions_org_id ON exception_resolutions (organization_id);

-- -----------------------------------------------------------------------------
-- 12. FORECASTS (Predictive Cash Flow Analytics & Volatility Bands)
-- -----------------------------------------------------------------------------
CREATE TABLE forecasts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    horizon forecast_horizon NOT NULL DEFAULT '30d',
    currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    projected_cash NUMERIC(18, 4) NOT NULL,
    confidence NUMERIC(5, 4) NOT NULL,
    model_name VARCHAR(100) NOT NULL DEFAULT 'EWMA_OLS_HYBRID',
    analytics JSONB NOT NULL DEFAULT '{}'::jsonb,
    points JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX ix_forecasts_org_horizon ON forecasts (organization_id, horizon, created_at DESC);

-- -----------------------------------------------------------------------------
-- 13. AI INSIGHTS (Predictive Anomaly Detection & Risk Warnings)
-- -----------------------------------------------------------------------------
CREATE TABLE ai_insights (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    reconciliation_run_id UUID REFERENCES reconciliation_runs(id) ON DELETE SET NULL,
    transaction_id UUID REFERENCES transactions(id) ON DELETE SET NULL,
    category VARCHAR(100) NOT NULL,
    severity insight_severity NOT NULL DEFAULT 'medium',
    title VARCHAR(255) NOT NULL,
    explanation TEXT NOT NULL,
    score_details JSONB,
    is_dismissed BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX ix_ai_insights_org_id ON ai_insights (organization_id);
CREATE INDEX ix_ai_insights_run_id ON ai_insights (reconciliation_run_id);
CREATE INDEX ix_ai_insights_category ON ai_insights (category);
CREATE INDEX ix_ai_insights_severity ON ai_insights (severity);

-- -----------------------------------------------------------------------------
-- 14. AUDIT LOG (Immutable, Append-Only Compliance Record)
-- -----------------------------------------------------------------------------
CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    actor_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(100) NOT NULL,
    entity_id UUID,
    details JSONB,
    ip_address VARCHAR(45),
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX ix_audit_log_user_id ON audit_log (actor_id);
CREATE INDEX ix_audit_log_org_created ON audit_log (organization_id, created_at DESC);
CREATE INDEX ix_audit_log_action ON audit_log (organization_id, action);
CREATE INDEX ix_audit_log_entity ON audit_log (entity_type, entity_id);
