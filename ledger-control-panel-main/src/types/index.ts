export type TxStatus = "matched" | "exception" | "pending_review";
export type Role = "admin" | "manager" | "analyst" | "editor" | "viewer";

export interface User {
  id?: string;
  email?: string;
  name?: string;
  role?: Role | string;
  [k: string]: unknown;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  token?: string;
  access_token?: string;
  refresh_token?: string;
  expires_in?: number;
  token_type?: string;
  user: User;
}

export interface UploadResponse {
  upload_id: string;
  filename?: string;
  rows?: number;
  [k: string]: unknown;
}

export interface Transaction {
  id: string;
  date: string;
  description: string;
  amount: number;
  currency?: string;
  source: string;
  confidence: number | null;
  status: TxStatus;
  external_ref?: string | null;
  match_id?: string | null;
  match_method?: string | null;
  reason?: string | null;
}

export interface ReconcileSummary {
  total?: number;
  matched?: number;
  exceptions?: number;
  pending_review?: number;
  matched_value?: number;
  exception_value?: number;
  [k: string]: unknown;
}

export interface ReconcileRun {
  run_id: string;
  status: "queued" | "running" | "completed" | "failed";
  progress?: number;
  stage?: string;
  error?: string;
  summary?: ReconcileSummary;
  transactions?: Transaction[];
  created_at?: string;
}

export interface ExceptionCandidate {
  id?: string;
  date?: string;
  description?: string;
  amount?: number;
  source?: string;
  confidence?: number | null;
}

export interface AiInsight {
  type: string;
  severity?: "low" | "medium" | "high";
  message: string;
}

/** Run-level AI insight returned by the backend insights endpoint. */
export interface RunInsight extends AiInsight {
  id?: string;
  title?: string;
  exception_id?: string | null;
  transaction_id?: string | null;
}

export interface LedgerException {
  id: string;
  date: string;
  description: string;
  amount: number;
  confidence: number | null;
  status: TxStatus;
  reason: string;
  best_candidate?: ExceptionCandidate | null;
  statement_side?: ExceptionCandidate | null;
  ledger_side?: ExceptionCandidate | null;
  ai_explanation?: string | null;
  insights?: AiInsight[];
}

export interface ForecastPoint {
  date: string;
  cash: number;
  projected?: number | null;
  lower?: number | null;
  upper?: number | null;
}

export interface ForecastResponse {
  horizon: string;
  currency?: string;
  projected_cash?: number;
  confidence?: number | null;
  points: ForecastPoint[];
}

export interface AskResponse {
  answer: string;
  supporting_rows: Array<Record<string, unknown>>;
}

export interface AuditEntry {
  id: string;
  timestamp: string;
  actor: string;
  action: string;
  details?: string | Record<string, unknown> | null;
}
