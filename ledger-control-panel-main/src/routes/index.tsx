import { createFileRoute } from "@tanstack/react-router";
import {
  Activity,
  ChevronLeft,
  ChevronRight,
  Download,
  Filter,
  Play,
  RotateCcw,
  Search,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import { ConfidenceDistribution } from "@/components/ConfidenceDistribution";
import { ReconciliationSummaryChart } from "@/components/ReconciliationSummaryChart";
import { EmptyState, ErrorState, LoadingState } from "@/components/DataState";
import { Metric, Panel } from "@/components/Panel";
import { TransactionDetail } from "@/components/TransactionDetail";
import { TransactionTable } from "@/components/TransactionTable";
import { UploadSlot, type UploadSlotState } from "@/components/UploadSlot";
import { DocumentUploadCard } from "@/components/DocumentUploadCard";
import { Can } from "@/components/Can";
import { AppShell } from "@/layouts/AppShell";
import { useRun } from "@/context/run";
import { ApiError, tokenStore, API_BASE_URL } from "@/lib/api";
import { formatMoney } from "@/lib/format";
import {
  getRun,
  getTransactions,
  startReconcile,
  uploadLedger,
  uploadStatement,
} from "@/services/ledger";
import type { ReconcileRun, Transaction, TxStatus } from "@/types";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Reconcile — Ledger Control" },
      {
        name: "description",
        content:
          "Upload bank statement and gateway ledger CSVs, run deterministic and AI-assisted reconciliation, and review scored transaction matches.",
      },
      { property: "og:title", content: "Reconcile — Ledger Control" },
      {
        property: "og:description",
        content:
          "Run reconciliation across bank statements and gateway ledgers with confidence scoring.",
      },
    ],
  }),
  component: ReconcilePage,
});

const IDLE: UploadSlotState = { file: null, uploadId: null, status: "idle" };
const POLL_MS = 2500;
const PAGE_SIZE = 25;

function ReconcilePage() {
  const { runId, setRunId } = useRun();
  const [statement, setStatement] = useState<UploadSlotState>(IDLE);
  const [ledger, setLedger] = useState<UploadSlotState>(IDLE);
  const [run, setRun] = useState<ReconcileRun | null>(null);
  const [starting, setStarting] = useState(false);
  const [rows, setRows] = useState<Transaction[] | null>(null);
  const [rowsError, setRowsError] = useState<string | null>(null);
  const [rowsLoading, setRowsLoading] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | TxStatus>("all");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [detail, setDetail] = useState<Transaction | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const loadRows = useCallback(async (id: string) => {
    setRowsLoading(true);
    setRowsError(null);
    try {
      const data = await getTransactions(id);
      setRows(data);
    } catch (err) {
      setRows(null);
      setRowsError(err instanceof Error ? err.message : "Could not load transactions.");
    } finally {
      setRowsLoading(false);
    }
  }, []);

  const handleExportCsv = useCallback(async () => {
    try {
      const token = tokenStore.get();
      const url = `${API_BASE_URL}/transactions/export${runId ? `?run_id=${runId}` : ""}`;
      const res = await fetch(url, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) throw new Error("Export failed.");
      const blob = await res.blob();
      const blobUrl = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = blobUrl;
      a.download = `transactions-${runId || "all"}-${Date.now()}.csv`;
      a.click();
      window.URL.revokeObjectURL(blobUrl);
      toast.success("Transaction report exported successfully.");
    } catch {
      toast.error("Failed to export transaction report.");
    }
  }, [runId]);

  // Reconciliation is asynchronous: poll the run until completion or failure.
  const poll = useCallback(
    async (id: string) => {
      try {
        const next = await getRun(id);
        setRun(next);
        setRunError(null);
        if (next.status === "completed") {
          if (Array.isArray(next.transactions) && next.transactions.length > 0) {
            setRows(next.transactions);
            setRowsError(null);
          } else {
            void loadRows(id);
          }
          toast.success("Reconciliation run completed");
          return;
        }
        if (next.status === "failed") {
          toast.error(next.error || "Reconciliation run failed");
          return;
        }
        timerRef.current = setTimeout(() => void poll(id), POLL_MS);
      } catch (err) {
        const message = err instanceof Error ? err.message : "Run status unavailable.";
        setRunError(message);
        if (!(err instanceof ApiError && err.isUnauthorized)) {
          timerRef.current = setTimeout(() => void poll(id), POLL_MS * 2);
        }
      }
    },
    [loadRows],
  );

  // Auto-load latest baseline run and transaction log on initial mount
  useEffect(() => {
    if (!runId) {
      void getRun("latest")
        .then((latest) => {
          if (latest) {
            setRun(latest);
            setRunId(latest.run_id);
            void loadRows(latest.run_id);
          } else {
            void loadRows("");
          }
        })
        .catch(() => {
          void loadRows("");
        });
    }
  }, [runId, loadRows, setRunId]);

  useEffect(() => {
    if (!runId) return;
    void poll(runId);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [runId, poll]);

  async function handleUpload(kind: "statement" | "ledger", file: File) {
    const setState = kind === "statement" ? setStatement : setLedger;
    setState({ file, uploadId: null, status: "uploading", error: null });
    try {
      const res = kind === "statement" ? await uploadStatement(file) : await uploadLedger(file);
      setState({
        file,
        uploadId: res.upload_id ?? null,
        rows: res.rows ?? null,
        status: "ready",
        error: null,
      });
      toast.success(`${kind === "statement" ? "Bank statement" : "Gateway ledger"} accepted`);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Upload rejected.";
      setState({ file, uploadId: null, status: "error", error: message });
      toast.error(message);
    }
  }

  async function handleRun() {
    setStarting(true);
    setRunError(null);
    try {
      const res = await startReconcile({
        statement_upload_id: statement.uploadId ?? undefined,
        ledger_upload_id: ledger.uploadId ?? undefined,
      });
      setRows(null);
      setRun(res);
      if (res.run_id) {
        setRunId(res.run_id);
        toast.success("Reconciliation queued");
      } else {
        toast.error("Backend did not return a run id.");
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Could not start reconciliation.";
      setRunError(message);
      toast.error(message);
    } finally {
      setStarting(false);
    }
  }

  function resetRun() {
    if (timerRef.current) clearTimeout(timerRef.current);
    setRunId(null);
    setRun(null);
    setRows(null);
    setRowsError(null);
    setRunError(null);
    setStatement(IDLE);
    setLedger(IDLE);
  }

  const canRun = statement.status === "ready" && ledger.status === "ready" && !starting;
  const running = run?.status === "queued" || run?.status === "running";
  const summary = run?.summary;

  const filtered = useMemo(() => {
    if (!rows) return [];
    const q = query.trim().toLowerCase();
    return rows.filter((r) => {
      if (filter !== "all" && r.status !== filter) return false;
      if (!q) return true;
      return (
        r.description.toLowerCase().includes(q) ||
        r.source.toLowerCase().includes(q) ||
        r.id.toLowerCase().includes(q) ||
        String(r.amount).includes(q) ||
        (r.external_ref ?? "").toLowerCase().includes(q)
      );
    });
  }, [rows, filter, query]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const currentPage = Math.min(page, pageCount);
  const paged = useMemo(
    () => filtered.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE),
    [filtered, currentPage],
  );

  useEffect(() => {
    setPage(1);
    setActiveIndex(-1);
  }, [filter, query, rows]);

  return (
    <AppShell
      title="Reconciliation Terminal"
      description="Dual-stream transaction matching, fuzzy scoring engine, and automated exception isolation."
    >
      <div className="space-y-4">
        {/* Upload Rails */}
        <div className="grid gap-3 md:grid-cols-2">
          <UploadSlot
            code="STREAM_01"
            title="Bank Statement (Cash Position)"
            description="Cash-side source of truth from banking partner statements."
            state={statement}
            disabled={running}
            onSelect={(f) => void handleUpload("statement", f)}
            onRemove={() => setStatement(IDLE)}
          />
          <UploadSlot
            code="STREAM_02"
            title="Gateway Ledger (Settlements)"
            description="Payment gateway and internal ledger transaction logs."
            state={ledger}
            disabled={running}
            onSelect={(f) => void handleUpload("ledger", f)}
            onRemove={() => setLedger(IDLE)}
          />
        </div>

        <Can permission="documents.create">
          <DocumentUploadCard />
        </Can>

        {/* Run Control Panel */}
        <Panel
          title="Reconciliation Engine Control"
          subtitle={
            runId
              ? `active run_id: ${runId} · status: ${run?.status ?? "polling"}`
              : "Both data streams required to initiate engine execution"
          }
          actions={
            <Can permission="reconciliation.execute">
              <div className="flex items-center gap-2">
                {runId ? (
                  <button
                    type="button"
                    onClick={resetRun}
                    className="lc-btn lc-btn--secondary text-xs"
                  >
                    <RotateCcw className="size-3.5" aria-hidden />
                    New Run
                  </button>
                ) : null}
                <button
                  type="button"
                  onClick={() => void handleRun()}
                  disabled={!canRun || running}
                  className="lc-btn lc-btn--primary text-xs"
                >
                  <Play className="size-3.5" aria-hidden />
                  {running
                    ? "Running reconciliation…"
                    : starting
                      ? "Initiating..."
                      : "Execute Reconciliation"}
                </button>
              </div>
            </Can>
          }
        >
          {running ? (
            <div className="px-4 py-4">
              <div className="flex items-center justify-between">
                <p className="label-micro flex items-center gap-2 text-[var(--ledger-primary)]">
                  <Activity className="size-4 animate-pulse" aria-hidden />
                  Dual-Stream Scoring Engine Active
                </p>
                <span className="num text-xs font-mono text-[var(--ledger-text-muted)]">
                  {run?.stage ?? "matching"}
                </span>
              </div>
              <div className="mt-2.5 h-1.5 w-full overflow-hidden rounded-full bg-[var(--ledger-surface-elevated)] border border-[var(--ledger-border)]">
                <div className="h-full w-1/2 animate-[shimmer_1.5s_infinite] rounded-full bg-[var(--ledger-primary)]" />
              </div>
            </div>
          ) : null}

          {summary ? (
            <div className="grid grid-cols-2 divide-x divide-[var(--ledger-border)] border-t border-[var(--ledger-border)] sm:grid-cols-4 bg-[var(--ledger-surface)]">
              <Metric
                label="Matched Records"
                value={String(summary.matched ?? 0)}
                {...(summary.matched_value != null
                  ? { hint: formatMoney(summary.matched_value) }
                  : {})}
                tone="verify"
              />
              <Metric
                label="Pending Review"
                value={String(summary.pending_review ?? 0)}
                tone="amber"
              />
              <Metric
                label="Isolated Exceptions"
                value={String(summary.exceptions ?? 0)}
                {...(summary.exception_value != null
                  ? { hint: formatMoney(summary.exception_value) }
                  : {})}
                tone="risk"
              />
              <Metric
                label="Total Reconciled"
                value={String(summary.total ?? 0)}
                hint={`Rate: ${Math.round(((summary.matched ?? 0) / (summary.total || 1)) * 100)}%`}
              />
            </div>
          ) : null}
        </Panel>

        {runError ? <ErrorState message={runError} /> : null}

        {summary ? (
          <div className="grid gap-4 md:grid-cols-2">
            <ReconciliationSummaryChart summary={summary} />
            {rows && rows.length > 0 ? <ConfidenceDistribution rows={rows} /> : null}
          </div>
        ) : null}

        {/* Transaction Ledger Table */}
        <Panel
          title="Reconciled Transaction Log"
          subtitle={
            rows
              ? `${filtered.length} of ${rows.length} records matching criteria`
              : "Execute a run or select an existing run to inspect records"
          }
          actions={
            <div className="flex flex-wrap items-center gap-2">
              <div className="relative">
                <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-[var(--ledger-text-muted)]" />
                <input
                  type="search"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Filter records..."
                  aria-label="Filter transactions"
                  className="lc-input pl-8 w-48 text-xs"
                />
              </div>

              <div className="flex items-center gap-1">
                <Filter className="size-3.5 text-[var(--ledger-text-muted)]" />
                <select
                  value={filter}
                  onChange={(e) => setFilter(e.target.value as "all" | TxStatus)}
                  aria-label="Filter by status"
                  className="lc-select text-xs"
                >
                  <option value="all">All Statuses</option>
                  <option value="matched">Matched</option>
                  <option value="pending_review">Pending Review</option>
                  <option value="exception">Exceptions</option>
                </select>
              </div>

              <button
                type="button"
                onClick={handleExportCsv}
                className="lc-btn lc-btn--secondary text-xs"
              >
                <Download className="size-3.5" />
                Export CSV
              </button>
            </div>
          }
        >
          {rowsLoading ? (
            <LoadingState label="Loading transaction stream" />
          ) : rowsError ? (
            <ErrorState
              message={rowsError}
              {...(runId
                ? {
                    onRetry: () => {
                      void loadRows(runId);
                    },
                  }
                : {})}
            />
          ) : !rows ? (
            <EmptyState
              title="No active reconciliation"
              description="Upload CSV statements above and execute the matching engine."
            />
          ) : filtered.length === 0 ? (
            <EmptyState
              title="No matching transactions"
              description="No records match your filter criteria. Reset the filter or query."
            />
          ) : (
            <>
              <TransactionTable
                rows={paged}
                activeIndex={activeIndex}
                onActiveIndexChange={setActiveIndex}
                onOpen={(tx) => setDetail(tx)}
              />

              {pageCount > 1 ? (
                <div className="flex items-center justify-between border-t border-[var(--ledger-border)] px-4 py-3 bg-[var(--ledger-surface)]">
                  <p className="label-micro text-[var(--ledger-text-muted)]">
                    Page{" "}
                    <span className="num font-bold text-[var(--ledger-text)]">{currentPage}</span>{" "}
                    of <span className="num font-bold text-[var(--ledger-text)]">{pageCount}</span>
                  </p>
                  <div className="flex items-center gap-1.5">
                    <button
                      type="button"
                      disabled={currentPage <= 1}
                      onClick={() => setPage((p) => Math.max(1, p - 1))}
                      className="lc-btn lc-btn--secondary text-xs py-1 px-2.5"
                    >
                      <ChevronLeft className="size-3.5" />
                      Prev
                    </button>
                    <button
                      type="button"
                      disabled={currentPage >= pageCount}
                      onClick={() => setPage((p) => Math.min(pageCount, p + 1))}
                      className="lc-btn lc-btn--secondary text-xs py-1 px-2.5"
                    >
                      Next
                      <ChevronRight className="size-3.5" />
                    </button>
                  </div>
                </div>
              ) : null}
            </>
          )}
        </Panel>
      </div>

      <TransactionDetail transaction={detail} onClose={() => setDetail(null)} />
    </AppShell>
  );
}
