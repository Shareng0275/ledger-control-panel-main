# Ledger Control — Ingest & Reconciliation Technical Guide

This guide documents the technical architecture, data contracts, and backend engineering requirements for uploading and reconciling **Bank Statement CSV** and **Gateway / Ledger CSV** files.

---

## 1. Expected Matching & KPI Metrics

When [`SAMPLE_BANK_STATEMENT.csv`](./SAMPLE_BANK_STATEMENT.csv) and [`SAMPLE_GATEWAY_LEDGER.csv`](./SAMPLE_GATEWAY_LEDGER.csv) are uploaded into the Ledger Control pipeline, the system produces deterministic reconciliation metrics:

| Dashboard KPI Metric | Target Value | Explanation / Mathematical Derivation |
|---|---|---|
| **Total Batched** | `30 records` | 15 Statement rows + 15 Ledger rows |
| **Reconciled Value** | `$154,541.50` | Sum of all matched and confirmed transaction volumes |
| **Auto-Matched** | `11 pairs (73.3%)` | 5 Exact Deterministic Matches + 6 High-Confidence AI Fuzzy Matches |
| **Discrepancies / Exceptions** | `8 records` | Unmatched items, fee deduction breaks, and unmatched book entries |
| **Average Match Confidence** | `96.8%` | Weighted mean confidence across all verified match pairs |

---

## 2. Backend Pipeline Workflow & Engineering Architecture

The backend executes an automated multi-stage processing pipeline:

```
[Bank Statement CSV] ──► [Upload & Ingest API]
                               │
[Gateway Ledger CSV] ──► [Upload & Ingest API]
                               │
                               ▼
            ┌──────────────────────────────────────┐
            │ Stage 1: Data Normalization Engine   │
            │ • UTC Date Serialization             │
            │ • Fixed-point Decimal Amount Parse   │
            │ • Vendor Name Noise Stripping        │
            │ • SHA-256 Idempotency Hashing        │
            └──────────────────┬───────────────────┘
                               │
                               ▼
            ┌──────────────────────────────────────┐
            │ Stage 2: Pass 1 Deterministic Rules  │
            │ • Rule 1: Exact Reference + Amount   │
            │ • Rule 2: Exact Amount + Date + Desc │
            │ • Rule 3: Amount + Desc (±2 Days)    │
            └──────────────────┬───────────────────┘
                               │
                               ▼
            ┌──────────────────────────────────────┐
            │ Stage 3: Pass 2 AI Fuzzy Scorer      │
            │ • Amount Exactness Score  (40%)      │
            │ • Date Proximity Score    (25%)      │
            │ • Description Similarity  (25%)      │
            │ • Reference Alignment     (10%)      │
            │                                      │
            │   Score >= 0.88 ──► Auto-Match       │
            │   0.65 to 0.87  ──► Review Drawer    │
            │   Score < 0.65  ──► Open Exception   │
            └──────────────────┬───────────────────┘
                               │
                               ▼
            ┌──────────────────────────────────────┐
            │ Stage 4: Exceptions & Audit Logging  │
            │ • Discrepancy Triage Table           │
            │ • Manual Side-by-Side Review Drawer  │
            │ • Immutable Chronological Audit Trail │
            └──────────────────────────────────────┘
```

---

## 3. Ingestion Data Contract (CSV Specifications)

### A. Bank Statement CSV Headers (`SAMPLE_BANK_STATEMENT.csv`)
* `date`: ISO date `YYYY-MM-DD` or standard US `MM/DD/YYYY`.
* `description`: Raw transaction narrative from clearing bank.
* `amount`: Positive decimal for credits/deposits, negative for debits/withdrawals.
* `currency`: 3-letter ISO code (e.g., `USD`, `INR`, `EUR`).
* `reference`: Bank UTR, wire reference, or gateway settlement ID.
* `transaction_type`: `credit` or `debit`.

### B. Gateway / Ledger CSV Headers (`SAMPLE_GATEWAY_LEDGER.csv`)
* `date`: Booking date in general ledger.
* `description`: Internal accounting ledger memo or vendor title.
* `amount`: Signed decimal matching general ledger entry.
* `currency`: 3-letter ISO code.
* `reference`: Internal invoice ID, purchase order, or gateway settlement ID.
* `transaction_type`: `credit` or `debit`.

---

## 4. API Endpoints for File Upload & Reconciliation

### 1. Upload Bank Statement
```http
POST /api/v1/uploads/statement HTTP/1.1
Authorization: Bearer <JWT_TOKEN>
Content-Type: multipart/form-data; boundary=----WebKitFormBoundary

------WebKitFormBoundary
Content-Disposition: form-data; name="file"; filename="SAMPLE_BANK_STATEMENT.csv"
Content-Type: text/csv

<CSV_DATA>
------WebKitFormBoundary--
```

### 2. Upload Gateway / Ledger
```http
POST /api/v1/uploads/ledger HTTP/1.1
Authorization: Bearer <JWT_TOKEN>
Content-Type: multipart/form-data; boundary=----WebKitFormBoundary

------WebKitFormBoundary
Content-Disposition: form-data; name="file"; filename="SAMPLE_GATEWAY_LEDGER.csv"
Content-Type: text/csv

<CSV_DATA>
------WebKitFormBoundary--
```

### 3. Trigger Two-Pass Reconciliation Job
```http
POST /api/v1/reconcile/run HTTP/1.1
Authorization: Bearer <JWT_TOKEN>
Content-Type: application/json

{
  "statement_upload_id": "UPLOAD_UUID_STATEMENT",
  "ledger_upload_id": "UPLOAD_UUID_LEDGER"
}
```

### 4. Fetch Live Reconciliation Dashboard & KPIs
```http
GET /api/v1/reconcile/{run_id} HTTP/1.1
Authorization: Bearer <JWT_TOKEN>
```
