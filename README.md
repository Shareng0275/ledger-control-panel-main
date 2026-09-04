# Ledger Control — AI Finance Controller

**Track**: AI Finance Controller — Razorpay AI Buildathon  
**Frontend Application**: [http://localhost:5173](http://localhost:5173)  
**Backend API & Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Overview

**Ledger Control** is an enterprise-grade financial reconciliation control tower designed for finance controllers, treasury leads, and CFOs. In modern multi-rail transaction environments, reconciling high-volume bank settlement statements against payment gateway records (e.g., Razorpay, Stripe) and internal ERP general ledgers is notoriously prone to manual error, timing lags, fee variances, and delayed closes.

Ledger Control automates this lifecycle using a strict **two-pass reconciliation architecture**:
1. **Pass 1 — Deterministic Exact Matching**: High-speed, mathematical rule matching for unequivocal transactions.
2. **Pass 2 — Explainable AI/Fuzzy Matching**: Multi-dimensional token similarity, date proximity, and fee variance scoring for unresolved records.

Records that do not meet high-confidence thresholds automatically triage into an interactive **Exception Review Drawer** for manual or bulk approval, backed by an **immutable audit trail**, **predictive cash flow forecasting**, and a **governed natural language financial assistant**.

---

## Architecture

The system operates on an asynchronous, decoupled client-server architecture where the backend database serves as the absolute single source of truth:

```
┌─────────────────────────────────────────────────────────────┐
│               LOVABLE FINANCIAL CONTROL TERMINAL            │
│         (React 18 + Vite + TanStack Router + Tailwind)      │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTPS / Bearer JWT / JSON
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                    ANTIGRAVITY BACKEND API                  │
│   (FastAPI / Express + SQLAlchemy Async + RapidFuzz + LLM)  │
├──────────────────────────────┬──────────────────────────────┤
│  • Normalization Engine      │  • Cash Forecasting (EWMA)   │
│  • Deterministic Rules (1-4) │  • Governed AI Assistant     │
│  • Fuzzy Scorer (4-Vector)   │  • Anomaly Detectors         │
│  • Exception Triage Router   │  • Immutable Audit Logger    │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│             POSTGRESQL 16+ MULTI-TENANT DATABASE            │
│  (Row-Level Org Partitioning, UUID PKs, NUMERIC(18,4), JSONB)│
└─────────────────────────────────────────────────────────────┘
```

---

## Technology Stack

- **Backend API**: Python 3.11 / FastAPI (with asynchronous worker pipelines and OpenAPI 3.1 contract compliance).
- **Matching & Similarity Engines**: RapidFuzz (C++ accelerated token/Levenshtein algorithms) + statistical decimal scoring.
- **Database & ORM**: PostgreSQL 16+ (SQLAlchemy 2.0 Async / Prisma ORM) with exact `NUMERIC(18, 4)` precision.
- **Frontend UI**: React 18, TypeScript, Vite, TanStack Router, Lucide Icons, and Sonner notifications.
- **Security**: Argon2id password hashing, JWT access + refresh rotation, rate limiting, and HTTP security headers.
- **Forecasting & Anomaly Detection**: Exponentially Weighted Moving Average (EWMA) + Ordinary Least Squares (OLS) drift models.

---

## Setup

### Prerequisites
- Python 3.11+
- Node.js 18+ or Bun
- PostgreSQL 16+ (or local zero-config SQLite for sandbox development)

### Step 1: Clone and Configure Environment
```bash
cp .env.example .env
```

### Step 2: Backend Setup & Seeding
```bash
cd backend
python -m venv .venv

# On Windows:
.\.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

pip install -e .
python seed.py
```

### Step 3: Frontend Setup
```bash
cd ../ledger-control-panel-main
npm install
```

---

## Environment Variables

The application is configured through environment variables documented in [`.env.example`](./.env.example):

| Variable | Description | Default / Example |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://postgres:postgres@localhost:5432/ledger_control` |
| `SECRET_KEY` | JWT signing secret key (min 32 chars) | `insecure-dev-secret-key-replace-in-production` |
| `ACCESS_TOKEN_EXPIRE_MINUTES`| Lifespan of JWT access tokens | `15` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Lifespan of rotating refresh tokens | `30` |
| `FUZZY_AUTO_MATCH_THRESHOLD` | Threshold for automatic fuzzy match | `0.88` |
| `FUZZY_REVIEW_THRESHOLD` | Threshold for pending review triage | `0.65` |
| `VITE_API_BASE_URL` | Base API URL consumed by frontend | `http://localhost:8000/api/v1` |

---

## Database

The PostgreSQL schema (`schema.sql`) implements row-level tenant partitioning via `organization_id` on all tables:
- `organizations` & `users`: Multi-tenant workspace and identity records.
- `memberships`: Role-based access control (`admin`, `analyst`, `viewer`).
- `uploads`: Bank Statement and Gateway Ledger CSV ingestion records.
- `transactions`: Normalized financial records with exact `NUMERIC(18, 4)` decimal precision.
- `reconciliation_runs`: Asynchronous job execution states and KPI summaries.
- `matches`: 1-to-1 match locks with granular score breakdowns (`JSONB`).
- `exceptions` & `exception_resolutions`: Discrepancy lifecycle and manual resolution audit entries.
- `forecasts` & `ai_insights`: Predictive cash metrics, volatility bounds, and anomaly cards.
- `audit_log`: Append-only compliance log for all financial events.

---

## Reconciliation Engine

The platform executes a two-pass matching strategy designed to guarantee mathematical safety while resolving real-world ambiguities:

### Pass 1: Deterministic Exact Matching (Highest Priority)
- **Rule 1 (Exact Reference)**: Matches statement and ledger records with identical normalized external reference numbers.
- **Rule 2 (Amount + Exact Date)**: Matches records with identical monetary amounts and calendar dates.
- **Rule 3 (Amount + Normalized Description)**: Matches records with identical amounts and sanitized vendor descriptions.
- **Rule 4 (Date Tolerance)**: Matches records with identical amounts within a configurable $\pm 2$ business day settlement window.
- **1-to-1 Conflict Lock**: Prevents duplicate matching; already-paired records are locked from subsequent rules.

### Pass 2: AI / Fuzzy Matching & Confidence Scoring
For records remaining unmatched after Pass 1, candidate pairs are generated within constrained date/amount windows and scored using a 4-feature weighted vector:
$$\text{Confidence Score} = (0.35 \cdot S_{\text{amount}}) + (0.30 \cdot S_{\text{description}}) + (0.25 \cdot S_{\text{date}}) + (0.10 \cdot S_{\text{reference}})$$

- **Auto-Match ($\ge 0.88$)**: Automatically finalized as a fuzzy match with full scoring explanation.
- **Pending Review ($0.65 - 0.87$)**: Triaged to the Exception Review Drawer for analyst inspection.
- **Open Exception ($< 0.65$)**: Flagged as high-risk discrepancy requiring manual intervention.

---

## API

All endpoints follow RESTful conventions under the `/api/v1` prefix with Bearer JWT authentication:

- **Authentication**: `POST /auth/login`, `POST /auth/register`, `POST /auth/refresh`, `POST /auth/logout`, `GET /auth/me`
- **Uploads**: `POST /uploads/statement`, `POST /uploads/ledger`
- **Reconciliation**: `POST /reconcile/run`, `GET /reconcile/{id}`, `GET /reconcile/{id}/summary`
- **Transactions**: `GET /transactions`, `GET /transactions/{id}`
- **Exceptions**: `GET /exceptions`, `GET /exceptions/{id}`, `POST /exceptions/{id}/resolve`, `POST /exceptions/bulk-resolve`
- **Forecast**: `GET /forecast?horizon=7d|30d|90d`
- **AI Assistant**: `POST /ask`
- **Insights & Audit**: `GET /insights`, `GET /audit`, `GET /health`

---

## Running the Application

### 1. Launch the Backend API
```powershell
cd backend
.\.venv\Scripts\uvicorn app.main:app --reload --port 8000
```

### 2. Launch the Lovable Frontend UI
```powershell
cd ledger-control-panel-main
npm run dev
```

### 3. Sign In with Demo Credentials
Navigate to **[http://localhost:5173/login](http://localhost:5173/login)**:
- **Email**: `admin@ledgercontrol.com`
- **Password**: `Password123!`

---

## Demo Flow

1. **Sign In**: Log into the control tower as the Lead Financial Controller.
2. **Upload Datasets**: Ingest [`sample-statement.csv`](./sample-statement.csv) and [`sample-ledger.csv`](./sample-ledger.csv).
3. **Execute Reconciliation**: Click **Run Reconciliation** to initiate the two-pass engine.
4. **Inspect Dashboard KPIs**: Observe verified matched totals, exception counts, and confidence distributions.
5. **Resolve Exceptions**: Open the **Exception Drawer** to view candidate comparisons, AI scoring explanations, and confirm/reject breaks.
6. **Analyze Cash Forecast**: Toggle 7d, 30d, and 90d projections to inspect expanding volatility confidence bands.
7. **Query AI Assistant**: Ask natural language financial questions (`"Why did the international wire fail to reconcile?"`) and view supporting database rows.
8. **Verify Compliance**: Inspect the immutable audit log timeline for complete operational governance.

---

## Known Limitations

- **Asynchronous Task Workers**: In local development mode, background jobs run via FastAPI background tasks; production deployments recommend dedicated Redis/Celery/BullMQ workers.
- **Single Currency per Run**: Multi-currency auto-conversion is currently evaluated using base currency normalization.
- **File Format Support**: Ingestion is optimized for CSV files; OFX, QIF, and MT940 parsers are scheduled for future releases.

---

## Security

- **Strict Multi-Tenancy**: Organization membership verified on every request; cross-tenant IDOR access is completely blocked.
- **SQL Injection Immunity**: 100% pre-parameterized ORM queries with whitelisted sort columns.
- **Sanitized Error Responses**: Global error handlers return structured JSON without leaking tracebacks or internal credentials.
- **Append-Only Auditing**: Audit records cannot be modified or deleted via application endpoints.

---

## Future Improvements

- **Native Razorpay Settlement Sync**: Direct API polling of Razorpay Settlement APIs for automated continuous ledger sync.
- **ERP Webhooks & Connectors**: Pre-built connectors for NetSuite, QuickBooks, and SAP.
- **Multi-Entity Treasury Rollups**: Consolidated multi-subsidiary intercompany reconciliation.
