# API Contract Specification
## Project Name: Ledger Control — Enterprise REST API
**Base URL Prefix**: `/api/v1` (with `/v1` alias supported)  
**Security Scheme**: `Authorization: Bearer <JWT_ACCESS_TOKEN>`  
**Tenant Context Header**: `X-Organization-Id: <UUID>`

---

## 1. Global Standards & Envelope Formats

### 1.1 Standard Error Structure
Returned on all non-2xx responses (e.g., 400, 401, 403, 404, 409, 422, 429, 500):
```json
{
  "error": "ValidationError",
  "detail": "Request payload validation failed.",
  "status_code": 422,
  "code": "VALIDATION_FAILED",
  "details": [
    {
      "field": "horizon",
      "message": "Input should be '7d', '30d' or '90d'"
    }
  ]
}
```

### 1.2 Standard Pagination Wrapper
```json
{
  "items": [],
  "total": 150,
  "page": 1,
  "page_size": 25,
  "total_pages": 6,
  "has_next": true,
  "has_prev": false
}
```

---

## 2. Authentication & Sessions

### 2.1 Register New Organization & Admin User
`POST /api/v1/auth/register`
- **Auth**: Public
- **Request Body**:
  ```json
  {
    "email": "controller@acme.com",
    "password": "Password123!",
    "full_name": "Alex Mercer",
    "organization_name": "Acme Financial Corp"
  }
  ```
- **Response `201 Created`**:
  ```json
  {
    "access_token": "eyJhbGciOi...",
    "token": "eyJhbGciOi...",
    "refresh_token": "eyJhbGciOi...",
    "token_type": "bearer",
    "expires_in": 900,
    "user": {
      "id": "3ac9c8fe-19bb-4288-85d8-5219f4833ac9",
      "email": "controller@acme.com",
      "full_name": "Alex Mercer",
      "is_active": true,
      "created_at": "2026-08-31T10:00:00Z"
    }
  }
  ```

### 2.2 User Login
`POST /api/v1/auth/login`
- **Auth**: Public
- **Request Body**:
  ```json
  {
    "email": "controller@acme.com",
    "password": "Password123!"
  }
  ```
- **Response `200 OK`**: Same schema as `POST /auth/register`.

### 2.3 Refresh Access Token
`POST /api/v1/auth/refresh`
- **Auth**: Public
- **Request Body**:
  ```json
  {
    "refresh_token": "eyJhbGciOi..."
  }
  ```
- **Response `200 OK`**: Returns new access token and rotated refresh token.

### 2.4 User Logout & Session Revocation
`POST /api/v1/auth/logout`
- **Auth**: Bearer Token
- **Request Body**:
  ```json
  {
    "refresh_token": "eyJhbGciOi..."
  }
  ```
- **Response `200 OK`**:
  ```json
  {
    "status": "success",
    "message": "Session successfully revoked."
  }
  ```

---

## 3. Financial File Uploads

### 3.1 Ingest Bank Statement CSV
`POST /api/v1/uploads/statement`
- **Auth**: Bearer Token
- **Headers**: `X-Organization-Id: <UUID>`
- **Content-Type**: `multipart/form-data`
- **Body**: `file: <CSV File>`
- **Response `201 Created`**:
  ```json
  {
    "id": "c1f7b8d4-5112-4c6e-8212-0761e1bca012",
    "upload_id": "c1f7b8d4-5112-4c6e-8212-0761e1bca012",
    "filename": "bank_statement_aug2026.csv",
    "upload_type": "statement",
    "row_count": 150,
    "rows": 150,
    "status": "valid",
    "validation_errors": null,
    "created_at": "2026-08-31T10:00:00Z"
  }
  ```

### 3.2 Ingest Internal / Gateway Ledger CSV
`POST /api/v1/uploads/ledger`
- **Auth**: Bearer Token
- **Headers**: `X-Organization-Id: <UUID>`
- **Content-Type**: `multipart/form-data`
- **Body**: `file: <CSV File>`
- **Response `201 Created`**: Same schema as Statement upload with `upload_type: "ledger"`.

---

## 4. Deterministic & Fuzzy Reconciliation Engine

### 4.1 Trigger Asynchronous Reconciliation Matching Run
`POST /api/v1/reconcile/run`
- **Auth**: Bearer Token
- **Headers**: `X-Organization-Id: <UUID>`
- **Request Body**:
  ```json
  {
    "statement_upload_id": "c1f7b8d4-5112-4c6e-8212-0761e1bca012",
    "ledger_upload_id": "d2e8c9e5-6223-4d7f-9323-1872f2cdb123"
  }
  ```
- **Response `201 Created` / `202 Accepted`**:
  ```json
  {
    "id": "e3f9d0f6-7334-4e80-a434-298303dec234",
    "run_id": "e3f9d0f6-7334-4e80-a434-298303dec234",
    "status": "processing",
    "total_transactions": 300,
    "matched_count": 0,
    "exception_count": 0,
    "pending_review_count": 0,
    "total_value_reconciled": "0.0000",
    "average_confidence": null,
    "summary": {
      "total": 300,
      "matched": 0,
      "exceptions": 0,
      "pending_review": 0,
      "matched_value": 0.0,
      "exception_value": 0.0
    },
    "created_at": "2026-08-31T10:05:00Z"
  }
  ```

### 4.2 Poll Reconciliation Run Status
`GET /api/v1/reconcile/{run_id}` (and alias `GET /api/v1/reconcile/runs/{run_id}`)
- **Auth**: Bearer Token
- **Headers**: `X-Organization-Id: <UUID>`
- **Response `200 OK`**:
  ```json
  {
    "id": "e3f9d0f6-7334-4e80-a434-298303dec234",
    "run_id": "e3f9d0f6-7334-4e80-a434-298303dec234",
    "status": "complete",
    "total_transactions": 300,
    "matched_count": 280,
    "exception_count": 15,
    "pending_review_count": 5,
    "total_value_reconciled": "450250.7500",
    "average_confidence": "0.9850",
    "started_at": "2026-08-31T10:05:01Z",
    "completed_at": "2026-08-31T10:05:03Z",
    "summary": {
      "total": 300,
      "matched": 280,
      "exceptions": 15,
      "pending_review": 5,
      "matched_value": 450250.75,
      "exception_value": 12400.00
    }
  }
  ```

---

## 5. Transactions API

### 5.1 List & Search Transactions
`GET /api/v1/transactions`
- **Auth**: Bearer Token
- **Query Parameters**:
  - `page` *(default: 1)*
  - `page_size` *(default: 25, max: 100)*
  - `search` *(searches description, reference)*
  - `status` *(`matched`, `exception`, `pending_review`, `unmatched`)*
  - `source` *(`statement`, `ledger`)*
  - `run_id` *(filter by reconciliation run)*
  - `sort_by` *(`transaction_date`, `amount`, `confidence`, `status`)*
  - `sort_order` *(`asc`, `desc`)*
- **Response `200 OK`**:
  ```json
  {
    "items": [
      {
        "id": "9a01f8d2-1144-4288-8212-0761e1bca999",
        "date": "2026-08-15T00:00:00Z",
        "description": "Stripe Payout Settlement",
        "amount": 15450.00,
        "currency": "USD",
        "source": "statement",
        "status": "matched",
        "confidence": 1.0,
        "external_ref": "STRIPE-SETTLE-9901",
        "match_id": "7b01f8d2-2255-4288-8212-0761e1bca888",
        "match_method": "deterministic",
        "reason": "Rule 1: Exact Reference Match"
      }
    ],
    "transactions": [],
    "total": 300,
    "page": 1,
    "page_size": 25,
    "total_pages": 12,
    "has_next": true,
    "has_prev": false
  }
  ```

### 5.2 Get Transaction Detail
`GET /api/v1/transactions/{id}`
- **Auth**: Bearer Token
- **Response `200 OK`**: Returns single transaction with full counterpart match data and audit trail.

---

## 6. Exceptions & Manual Triage

### 6.1 List Reconciliation Exceptions
`GET /api/v1/exceptions`
- **Auth**: Bearer Token
- **Query Parameters**: `page`, `page_size`, `status`, `priority`, `run_id`, `sort_by`, `sort_order`
- **Response `200 OK`**:
  ```json
  {
    "items": [
      {
        "id": "5f01f8d2-3366-4288-8212-0761e1bca777",
        "reconciliation_run_id": "e3f9d0f6-7334-4e80-a434-298303dec234",
        "transaction_id": "9a01f8d2-1144-4288-8212-0761e1bca999",
        "date": "2026-08-20T00:00:00Z",
        "description": "Unknown International Wire Inflow",
        "amount": 7500.00,
        "currency": "USD",
        "status": "open",
        "priority": "high",
        "reason": "Unmatched wire inflow; candidate found with exact amount ($7,500.00)",
        "confidence": 0.72,
        "statement_side": {
          "id": "9a01f8d2-1144-4288-8212-0761e1bca999",
          "date": "2026-08-20T00:00:00Z",
          "description": "Unknown International Wire Inflow",
          "amount": 7500.00,
          "source": "statement"
        },
        "best_candidate": {
          "id": "8c01f8d2-4477-4288-8212-0761e1bca666",
          "date": "2026-08-20T00:00:00Z",
          "description": "Consulting Inflow Client Services",
          "amount": 7500.00,
          "source": "ledger",
          "confidence": 0.72
        }
      }
    ],
    "exceptions": [],
    "total": 15,
    "page": 1,
    "page_size": 25,
    "total_pages": 1,
    "has_next": false,
    "has_prev": false
  }
  ```

### 6.2 Get Exception Review Drawer Detail
`GET /api/v1/exceptions/{id}`
- **Auth**: Bearer Token
- **Response `200 OK`**: Returns `statement_transaction`, `candidate_transaction`, and `explanation_details` for side-by-side comparison.

### 6.3 Resolve Exception
`POST /api/v1/exceptions/{id}/resolve`
- **Auth**: Bearer Token
- **Request Body**:
  ```json
  {
    "action": "confirm_match",
    "candidate_id": "8c01f8d2-4477-4288-8212-0761e1bca666",
    "note": "Verified invoice and bank wire correspondence."
  }
  ```
- **Response `200 OK`**:
  ```json
  {
    "exception_id": "5f01f8d2-3366-4288-8212-0761e1bca777",
    "status": "resolved",
    "message": "Exception confirmed and matched successfully.",
    "match_id": "7b01f8d2-2255-4288-8212-0761e1bca888"
  }
  ```

---

## 7. Predictive Forecasting & AI Intelligence

### 7.1 Multi-Horizon Cash Flow Projections
`GET /api/v1/forecast?horizon=7d|30d|90d`
- **Auth**: Bearer Token
- **Query Parameter**: `horizon` *(Required: `7d`, `30d`, or `90d`)*
- **Response `200 OK`**:
  ```json
  {
    "horizon": "30d",
    "currency": "USD",
    "projected_cash": 1250000.50,
    "confidence": 0.88,
    "points": [
      {
        "date": "2026-09-01",
        "cash": 950000.00,
        "projected": 955000.00,
        "lower": 940000.00,
        "upper": 970000.00
      }
    ],
    "analytics": {
      "net_daily_drift": 4500.25,
      "historical_volatility": 15200.00,
      "historical_data_points": 90
    }
  }
  ```

### 7.2 Conversational AI Financial Assistant
`POST /api/v1/ask`
- **Auth**: Bearer Token
- **Request Body**:
  ```json
  {
    "question": "Which high-value transactions failed to reconcile last week?"
  }
  ```
- **Response `200 OK`**:
  ```json
  {
    "answer": "There is 1 high-value break: an unmatched international wire inflow of $7,500.00 on August 20.",
    "supporting_rows": [
      {
        "id": "9a01f8d2-1144-4288-8212-0761e1bca999",
        "amount": "7500.00",
        "description": "Unknown International Wire Inflow",
        "date": "2026-08-20T00:00:00Z",
        "status": "exception"
      }
    ]
  }
  ```

### 7.3 Predictive Anomaly Detection Insights
`GET /api/v1/insights`
- **Auth**: Bearer Token
- **Query Parameters**: `severity` *(`low`, `medium`, `high`, `critical`)*, `run_id`
- **Response `200 OK`**:
  ```json
  {
    "insights": [
      {
        "id": "1a01f8d2-9999-4288-8212-0761e1bca001",
        "type": "unusual_amount",
        "severity": "high",
        "message": "Transaction $45,000.00 is 3.8 standard deviations above the 30-day mean ($3,200.00).",
        "title": "Unusual Amount Outlier",
        "transaction_id": "9a01f8d2-1144-4288-8212-0761e1bca999"
      }
    ],
    "total": 1,
    "severity_counts": { "critical": 0, "high": 1, "medium": 0, "low": 0 }
  }
  ```

---

## 8. Compliance & Service Health

### 8.1 Immutable Audit Log
`GET /api/v1/audit`
- **Auth**: Bearer Token
- **Query Parameters**: `run_id`, `action`, `entity_type`, `start_date`, `end_date`, `page`, `page_size`
- **Response `200 OK`**:
  ```json
  {
    "items": [
      {
        "id": "4b01f8d2-8888-4288-8212-0761e1bca111",
        "timestamp": "2026-08-31T10:05:03Z",
        "actor": "Alex Mercer (Admin)",
        "action": "reconciliation.completed",
        "details": { "matched_count": 280, "exception_count": 15 }
      }
    ],
    "entries": [],
    "total": 45,
    "page": 1,
    "page_size": 25,
    "total_pages": 2
  }
  ```

### 8.2 Service Health Probe
`GET /health` (and `GET /api/v1/health`)
- **Auth**: Public
- **Response `200 OK`**:
  ```json
  {
    "status": "healthy",
    "app": "Ledger Control API",
    "version": "0.1.0",
    "database": "connected"
  }
  ```
