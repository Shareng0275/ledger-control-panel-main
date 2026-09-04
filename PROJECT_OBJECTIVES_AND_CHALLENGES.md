# Ledger Control — Project Objectives & Technical Challenges

A comprehensive overview of the core problems solved by **Ledger Control**, followed by the key architectural challenges, technical obstacles, and engineering solutions implemented during development.

---

## 🎯 Part 1: Project Objectives — What Does It Solve?

Financial teams face significant operational friction when attempting to reconcile high-volume bank accounts with multiple internal payment gateways (e.g., Stripe, PayPal, Adyen, Square). Ledger Control automates and secures this entire lifecycle:

### 1. Eliminates Manual Spreadsheet Reconciliation
* **Problem**: Finance operators spend hours manually cross-referencing banking transactions against payment gateway settlement exports in Excel.
* **Solution**: Ingests dual-stream financial records—**Bank Statements** (cash position) vs. **Gateway Ledgers** (settlement records)—and runs automated deterministic and fuzzy confidence scoring passes to match pairs in milliseconds.

### 2. Isolates Financial Discrepancies & Breaks
* **Problem**: Subtle fee deductions, multi-day bank settlement delays, and split payouts frequently create accounting breaks that go unnoticed until monthly closing.
* **Solution**: Automatically isolates mismatched items and routes them to an **Exception Resolution Queue**, providing automated AI root-cause diagnostics to highlight whether variance stems from gateway fees, timing lags, or missing records.

### 3. Predicts Future Cash Runway & Liquidity
* **Problem**: Financial models rely on static assumptions or backward-looking reports that quickly become obsolete.
* **Solution**: Features forward-looking statistical modeling that projects cash trajectories across **7-day, 30-day, and 90-day** horizons with 95% confidence intervals derived directly from settled ledger activity.

### 4. Grounded Financial AI Copilot (Zero Hallucination)
* **Problem**: Traditional conversational AI systems often fabricate numbers or cannot access verified corporate ledger records.
* **Solution**: A natural language copilot that allows operators to ask plain-English questions like *"What's my current cash position?"* or *"Show Stripe breaks > $500"*, backed strictly by parameterized SQL database lookups and supporting evidence tables.

### 5. Guarantees SOC-2 Audit Compliance
* **Problem**: Financial audits require strict, tamper-evident records of who modified, accepted, or overrode transactions.
* **Solution**: Every file ingestion, reconciliation run, manual break override, and role transition is cryptographically logged in an **Immutable Audit Ledger**.

---

## 🛠️ Part 2: Build Challenges & Technical Obstacles — Issues & Solutions

During development, several critical technical obstacles were encountered and resolved:

### 1. Onboarding Guide Permanently Disappearing or Spreading Across Tabs
* **Issue**: Storing a static `hasSeenGuide: true` flag in `localStorage` caused the guide to never fire again after initial dismissal, violating the requirement for the guide to activate on every login. Conversely, omitting persistence caused the guide to interrupt users on every route navigation within the same session.
* **Solution**: Implemented a **session-aware persistence architecture** using `sessionStorage` keyed by a fresh `sessionId` minted on each `auth.login`. Added `BroadcastChannel("lc_guide_broadcast_v1")` so step progress and dismissals sync across multi-tab sessions in real time.

### 2. Static Guide Content Across Different User Privileges
* **Issue**: The original onboarding guide was identical for all users, failing to inform users of their operational permissions or restrictions (e.g., Viewers seeing admin execution steps).
* **Solution**: Built a **dynamic role-mapping engine** that normalizes roles (`Administrator`, `Operational Editor`, `Read-Only Viewer`) and renders an interactive **Role Rules & Permissions Matrix** with color-coded badges (`Permitted` vs. `Restricted`). Added a reactive role observer (`prevRoleRef`) that adapts steps and notifications on the fly if a role changes mid-session.

### 3. Low Contrast & React Portal CSS Isolation
* **Issue**: Rendering the guide modal in a React portal outside the main DOM tree detached it from `.authenticated-app` styles, causing poor text contrast and invisible elements against dark backgrounds.
* **Solution**: Scoped `.onboarding-portal` directly to the portal root and applied explicit high-contrast theme tokens (`#141418` dark card, `#383846` border, violet glow, and `#FFFFFF` readable typography).

### 4. Dual-Runtime Database Compatibility (`bun:sqlite` vs. `node:sqlite`)
* **Issue**: Running the backend across multiple runtime environments (Bun in development/tests vs. Node.js on Windows) caused native C++ SQLite drivers (`better-sqlite3`) to fail during build and test execution.
* **Solution**: Created a zero-dependency runtime adapter in `sqliteDb.ts` that dynamically detects the engine and uses `bun:sqlite` in Bun and `node:sqlite` (`DatabaseSync`) in Node 22.

### 5. Large Dataset Ingestion & SQLite Disk Image Corruption
* **Issue**: The 500 MB PaySim log CSV caused file locks and OneDrive sync interruptions, leading to `SQLITE_CORRUPT` and exceeding GitHub's 100 MB upload limit.
* **Solution**: Implemented chunked streaming with sub-millisecond B-tree indexes, rebuilt a clean indexed database with 50,000 transactions and 100 fraud cases, and configured a root `.gitignore` to prevent giant binary files from blocking git pushes.

### 6. Reconciled Transaction Log Initial Empty State
* **Issue**: The transaction log displayed an empty state upon initial login because it required an active `run_id` to be selected before fetching records.
* **Solution**: Implemented fallback auto-fetching on mount so the 90-day multi-gateway baseline loads automatically with populated tables and summary metrics on first launch.

### 7. Hardcoded Keyword Matching in the AI Copilot
* **Issue**: The AI Copilot previously responded only to exact hardcoded questions with mock answers.
* **Solution**: Upgraded `aiService.ts` into a dynamic query engine that translates natural language prompts into parameterized database lookups against active transactions, cash balances, and variance records.

---

## 👥 Role Permissions Matrix Quick Reference

| Role | Reconciliation Execution | Exception Break Resolution | Forward Cash Forecasting | User & Role Governance | Audit Log Access |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Administrator** | ✅ Full Access | ✅ Full & Bulk Overrides | ✅ Full Access | ✅ Full Access | ✅ Full Audit & Exports |
| **Operational Editor** | ✅ Daily Ingestion & Runs | ✅ Resolve with Notes | ✅ Full Access | ❌ Restricted | ✅ View Audit Logs |
| **Read-Only Viewer** | ❌ Restricted | ❌ Restricted | ✅ Read-Only Projections | ❌ Restricted | ✅ Read-Only Logs |

---

*Repository: [https://github.com/Shareng0275/ledger-control-panel-main](https://github.com/Shareng0275/ledger-control-panel-main)*
