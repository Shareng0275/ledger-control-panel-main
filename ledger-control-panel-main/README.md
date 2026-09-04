# Ledger Control Panel

MASTER PROJECT SPECIFICATION

AI FINANCE CONTROLLER / LEDGER CONTROL

LOVABLE FRONTEND

You are the senior frontend architect and UI engineer responsible for building the complete production-quality frontend for an AI Finance Controller / Ledger Control application.

The application is a financial reconciliation and control platform.

PRIMARY WORKFLOW:

Bank Statement CSV

        ↓

Gateway/Ledger CSV

        ↓

Backend normalization

        ↓

Deterministic matching

        ↓

AI/LLM fuzzy matching

        ↓

Confidence scoring

        ↓

Exceptions

        ↓

Manual resolution

        ↓

Cash Forecast

        ↓

AI Financial Analysis

        ↓

Audit Trail

IMPORTANT ARCHITECTURAL RULE:

The backend is the single source of truth.

The frontend must NEVER invent:

- transactions

- reconciliation results

- confidence scores

- exceptions

- AI explanations

- forecasts

- audit records

- financial values

Static/mock data may be used ONLY temporarily during UI construction and must be removed before final integration.

==================================================

TECHNOLOGY

==================================================

Use:

React

TypeScript

Vite

Tailwind CSS

React Router

Lucide icons

shadcn/ui where useful

Fetch or Axios

Context API or lightweight state management

Recommended structure:

src/

  components/

  components/ui/

  layouts/

  pages/

  hooks/

  services/

  api/

  context/

  types/

  utils/

  lib/

Avoid unnecessary architectural complexity.

==================================================

LEDGER DESIGN SYSTEM

==================================================

The product name is:

LEDGER CONTROL

The visual identity must feel like:

financial control tower

reconciliation terminal

enterprise finance infrastructure

professional accounting operations system

DO NOT make it look like a generic SaaS dashboard.

Colors:

Background #0F1712

Surface #16211C

Verify Green #1F5F4F

Ledger Gold #B08D57

Exception Amber #C98A3A

Risk Red #B84C4C

Primary Text #EDEFEA

Muted Text #8A9A92

Semantic usage:

Green:

matched / verified / successful

Gold:

confidence / financial importance / forecast

Amber:

pending / review / warning

Red:

exception / failure / anomaly / high risk

Typography:

Headings:

Space Grotesk

Body/UI:

IBM Plex Sans

Financial numbers:

IBM Plex Mono

Financial values must use tabular numerals.

==================================================

SHAPE LANGUAGE

==================================================

Maximum border radius:

4px

Use:

1px borders

hairline separators

compact spacing

restrained shadows

dense data presentation

Never use:

purple/indigo Lovable defaults

Inter font

glassmorphism

large rounded cards

rounded-2xl

excessive gradients

cartoon illustrations

generic startup dashboard styling

excessive floating cards

==================================================

APPLICATION AREAS

==================================================

The final application contains exactly these primary areas:

1. Login

2. Reconcile

3. Exceptions

4. Forecast

5. Ask

6. Audit

Do not add unrelated product areas.

==================================================

AUTHENTICATION

==================================================

Backend authentication:

POST /v1/auth/login

Expected response:

{

  token,

  user

}

Frontend must provide:

login

logout

protected routes

session restoration

401 handling

expired-session handling

JWT must be attached to protected API calls.

API base URL:

VITE_API_BASE_URL

Default development value:

http://localhost:8000/api/v1

Never hardcode localhost throughout the application.

Never expose:

database credentials

LLM API keys

backend secrets

==================================================

RECONCILIATION

==================================================

Two uploads:

Bank Statement CSV

Gateway Ledger CSV

Endpoints:

POST /v1/uploads/statement

POST /v1/uploads/ledger

Start:

POST /v1/reconcile/run

Reconciliation is asynchronous.

The frontend must poll the backend until completion or failure.

Never assume immediate completion.

==================================================

TRANSACTIONS

==================================================

Transaction table contains:

Date

Description

Amount

Source

Confidence

Status

Statuses:

matched

exception

pending_review

Confidence must always display:

visual confidence bar

percentage

semantic color

Never display confidence as a naked percentage.

==================================================

EXCEPTIONS

==================================================

Exception workspace includes:

transaction

amount

date

confidence

status

reason

best candidate

Manual review provides:

statement side

ledger side

AI explanation

Resolution:

POST /v1/exceptions/:id/resolve

Support:

Confirm Match

Reject

Bulk confirmation

==================================================

AI INSIGHTS

==================================================

AI insights may include backend-provided:

unusual amount

unusual frequency

near duplicate

suspicious mismatch

high-risk exception

Never fabricate AI insights.

==================================================

FORECAST

==================================================

Endpoint:

GET /v1/forecast?horizon=<7d|30d|90d>

Display:

projected cash

confidence band

date

cash amount

Projected line uses Ledger Gold.

==================================================

ASK

==================================================

Endpoint:

POST /v1/ask

Request:

{

  question

}

Response:

{

  answer,

  supporting_rows[]

}

Never fabricate an AI answer.

==================================================

AUDIT

==================================================

Endpoint:

GET /v1/audit?run_id=<id>

Display:

timestamp

actor

action

details

Audit is read-only.

==================================================

GLOBAL UX RULES

==================================================

Every API-driven feature must support:

loading

success

empty

error

retry

Never show a blank page because an API failed.

Use professional toast notifications.

Use restrained animations under 200ms.

Support keyboard navigation.

Use responsive layouts.

==================================================

FINAL PRODUCT STANDARD

==================================================

The final frontend must look suitable for:

financial reconciliation

enterprise finance operations

technical review

AI buildathon demonstration

live product demonstration

The frontend must be polished, functional, responsive and backend-driven.

DO NOT turn this into a generic SaaS dashboard.

This project was built with [Lovable](https://lovable.dev).

## Build with Lovable

Continue developing this project in the [Lovable editor](https://lovable.dev/projects/072b0127-3b73-4578-b818-5fe9075799f9).

- **Ship faster**: describe what you want to build and Lovable handles the code.
- **Stay in sync**: every change made in Lovable is committed straight to this repository.
- **Full ownership**: this code is yours. Push to `main` on GitHub and your changes sync back into Lovable, ready for your next prompt.

## Development

Prefer working locally? You need Node.js and npm — [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating).

```sh
git clone <this-repository-url>
cd <repository-name>
npm i
npm run dev
```
