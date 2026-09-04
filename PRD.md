# LEDGER CONTROL — AI Finance Controller
**Product Requirements Document** | **Razorpay AI Buildathon: AI Finance Controller Track**

---

### 1. Product Overview & Problem Statement
**Ledger Control** is an autonomous financial reconciliation control tower designed for finance controllers, treasury leads, and CFOs. Modern businesses process thousands of transactions across banking partners and payment gateways (like Razorpay). Discrepancies caused by fee deductions, timing delays, missing references, and description mismatches cause delayed month-end closes, manual spreadsheet fatigue, and compliance risks. Ledger Control eliminates manual reconciliation by pairing deterministic matching rules with explainable AI fuzzy scoring and cash intelligence.

### 2. Target Users & Single Source of Truth
- **Target Users**: Financial Controllers, Treasury Managers, Accounting Leads, and CFOs.
- **System Authority**: The PostgreSQL backend acts as the strict single source of truth for all ledger balances, match pairs, and compliance states.

### 3. Core Reconciliation Pipeline
The platform ingests **Bank Statement CSV** and **Gateway/Ledger CSV** files through a 9-step automated pipeline:
1. **CSV Upload**: Ingestion of bank settlements and gateway payout ledgers.
2. **Validation**: Structural, encoding, size, and header integrity checks.
3. **Normalization**: Standardization of UTC timestamps, 4-decimal currency amounts, references, and descriptions.
4. **Deterministic Exact Matching**: Strict 1-to-1 matching via exact references, amounts, and dates.
5. **AI/LLM Fuzzy Matching**: Intelligent candidate generation for unresolved records evaluating token similarity, date proximity, and fee variances.
6. **Confidence Scoring**: Generation of weighted confidence scores (0.00–1.00) with detailed component explanations.
7. **Exception Creation**: Automatic triaging of low-confidence items (<0.88) into prioritized exceptions.
8. **Manual Review**: Interactive review drawer allowing single-click confirmation, candidate override, or rejection.
9. **Audit Logging**: Immutable, append-only compliance logging for all financial lifecycle events.

### 4. Advanced AI & Financial Capabilities
- **Cash Forecasting**: Multi-horizon statistical cash flow projections (7d, 30d, 90d) with expanding uncertainty bands.
- **AI Financial Assistant**: Secure natural language queries answered strictly with real supporting database rows.
- **Predictive Anomaly Detection**: Automated detection of unusual transaction amounts, frequency bursts, and suspicious mismatches.

### 5. Razorpay AI Buildathon Relevance & Core Demo Journey
Built specifically for the **AI Finance Controller** track, Ledger Control showcases end-to-end autonomous treasury operations:
- **Demo Journey**: Upload Settlement & Gateway CSVs $\to$ Automated 9-step match execution $\to$ Review AI-scored exceptions $\to$ Inspect 30-day cash forecast $\to$ Query AI Assistant for unmatched breaks $\to$ Verify immutable audit trail.
