# Ledger Control Backend API

Production-ready, multi-tenant financial reconciliation, forecasting, anomaly detection, and AI financial assistant backend built with **FastAPI**, **SQLAlchemy (Async)**, **PostgreSQL**, and **RapidFuzz**.

---

## Architecture Overview

- **Multi-Tenant Isolation**: Row-level tenant partitioning verified via `Membership` RBAC and `X-Organization-Id`.
- **Deterministic Reconciliation**: 4-rule deterministic pipeline (Exact reference, amount/date, amount/description, date tolerance) with 1-to-1 conflict prevention.
- **Explainable Fuzzy Matching**: 4-component RapidFuzz scorer with auto-match ($\ge 0.88$), review ($0.65-0.87$), and exception ($< 0.65$) triage.
- **Financial Precision**: All currency calculations use exact `Decimal` representation.
- **Predictive Anomaly Detection**: Robust Z-scores, frequency bursts, and suspicious mismatch detection.
- **Cash Forecasting**: Multi-horizon (7d, 30d, 90d) EWMA + linear drift with expanding volatility confidence bands.
- **AI Financial Assistant**: Secure scoped data retrieval without arbitrary dynamic SQL execution.
- **Immutable Audit Trail**: Append-only compliance logging across auth, uploads, reconciliation, triage, and AI.

---

## Getting Started

### 1. Environment Setup
```bash
cp .env.example .env
# Edit .env with your PostgreSQL credentials and SECRET_KEY
```

### 2. Install Dependencies
```bash
python -m venv .venv
# On Linux/macOS:
source .venv/bin/activate
# On Windows:
.\.venv\Scripts\activate

pip install -e .
```

### 3. Database Migrations
```bash
alembic upgrade head
```

### 4. Running the Development Server
```bash
uvicorn app.main:app --reload --port 8000
```

---

## Running Automated Tests

Run the complete 129-test automated suite (Unit, Integration, Security, E2E):
```bash
pytest -v
```

---

## Docker Deployment

### Start with Docker Compose (PostgreSQL + FastAPI):
```bash
docker-compose up -d --build
```

Health check available at:
```
GET http://localhost:8000/health
```

---

## API Endpoints Summary

- **Auth**: `POST /api/v1/auth/login`, `POST /refresh`, `POST /logout`, `GET /me`
- **Uploads**: `POST /api/v1/uploads/statement`, `POST /api/v1/uploads/ledger`
- **Reconciliation**: `POST /api/v1/reconcile/run`, `GET /reconcile/{id}`, `GET /reconcile/{id}/summary`
- **Transactions**: `GET /api/v1/transactions`, `GET /api/v1/transactions/{id}`
- **Exceptions**: `GET /api/v1/exceptions`, `GET /exceptions/{id}`, `POST /resolve`, `POST /bulk-resolve`
- **Forecast**: `GET /api/v1/forecast?horizon=7d|30d|90d`
- **AI Ask**: `POST /api/v1/ask`
- **Insights**: `GET /api/v1/insights`
- **Audit**: `GET /api/v1/audit`
- **Health**: `GET /health`, `GET /api/v1/health`
