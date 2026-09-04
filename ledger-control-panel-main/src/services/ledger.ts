import { apiRequest } from "@/lib/api";
import type {
  AskResponse,
  AuditEntry,
  ForecastResponse,
  LedgerException,
  ReconcileRun,
  RunInsight,
  Transaction,
  UploadResponse,
} from "@/types";

export async function getInsights(runId?: string | null, signal?: AbortSignal | undefined) {
  const qs = runId ? `?run_id=${encodeURIComponent(runId)}` : "";
  const payload = await apiRequest<unknown>(`/v1/insights${qs}`, { signal });
  return list<RunInsight>(payload, "insights");
}

function list<T>(payload: unknown, key: string): T[] {
  if (Array.isArray(payload)) return payload as T[];
  const rec = payload as Record<string, unknown> | null;
  const candidate = rec?.[key] ?? rec?.["items"] ?? rec?.["data"] ?? rec?.["results"];
  return Array.isArray(candidate) ? (candidate as T[]) : [];
}

export function uploadStatement(file: File) {
  const form = new FormData();
  form.append("file", file);
  return apiRequest<UploadResponse>("/v1/uploads/statement", { method: "POST", body: form });
}

export function uploadLedger(file: File) {
  const form = new FormData();
  form.append("file", file);
  return apiRequest<UploadResponse>("/v1/uploads/ledger", { method: "POST", body: form });
}

export function startReconcile(body: {
  statement_upload_id?: string | undefined;
  ledger_upload_id?: string | undefined;
}) {
  return apiRequest<ReconcileRun>("/v1/reconcile/run", { method: "POST", body });
}

export function getRun(runId: string, signal?: AbortSignal | undefined) {
  return apiRequest<ReconcileRun>(`/v1/reconcile/runs/${runId}`, { signal });
}

export async function getTransactions(runId?: string, signal?: AbortSignal | undefined) {
  const qs = runId && runId !== "all" ? `?run_id=${encodeURIComponent(runId)}` : "";
  const payload = await apiRequest<unknown>(`/v1/transactions${qs}`, { signal });
  return list<Transaction>(payload, "transactions");
}

export async function getExceptions(runId?: string | null, signal?: AbortSignal | undefined) {
  const qs = runId ? `?run_id=${encodeURIComponent(runId)}` : "";
  const payload = await apiRequest<unknown>(`/v1/exceptions${qs}`, { signal });
  return list<LedgerException>(payload, "exceptions");
}

export function getException(id: string, signal?: AbortSignal | undefined) {
  return apiRequest<LedgerException>(`/v1/exceptions/${id}`, { signal });
}

export function resolveException(
  id: string,
  body: {
    action: "confirm" | "reject";
    candidate_id?: string | undefined;
    note?: string | undefined;
  },
) {
  return apiRequest<{ status?: string }>(`/v1/exceptions/${id}/resolve`, { method: "POST", body });
}

export function getForecast(horizon: "7d" | "30d" | "90d", signal?: AbortSignal | undefined) {
  return apiRequest<ForecastResponse>(`/v1/forecast?horizon=${horizon}`, { signal });
}

export function ask(question: string) {
  return apiRequest<AskResponse>("/v1/ask", { method: "POST", body: { question } });
}

export async function getAudit(runId?: string | null, signal?: AbortSignal | undefined) {
  const qs = runId ? `?run_id=${encodeURIComponent(runId)}` : "";
  const payload = await apiRequest<unknown>(`/v1/audit${qs}`, { signal });
  return list<AuditEntry>(payload, "entries");
}
