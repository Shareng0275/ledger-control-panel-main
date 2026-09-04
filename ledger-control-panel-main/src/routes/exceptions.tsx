import { createFileRoute } from "@tanstack/react-router";
import {
  Check,
  ChevronLeft,
  ChevronRight,
  RefreshCw,
  AlertTriangle,
  ShieldCheck,
  Clock,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { AiInsightsPanel } from "@/components/AiInsightsPanel";
import { ConfidenceBar } from "@/components/ConfidenceBar";
import { EmptyState, ErrorState, LoadingState } from "@/components/DataState";
import { ExceptionDrawer } from "@/components/ExceptionDrawer";
import { Panel } from "@/components/Panel";
import { StatusChip } from "@/components/StatusChip";
import { Can } from "@/components/Can";
import { AppShell } from "@/layouts/AppShell";
import { useRun } from "@/context/run";
import { formatDate, formatMoney } from "@/lib/format";
import { cn } from "@/lib/utils";
import { getExceptions, resolveException } from "@/services/ledger";
import type { LedgerException } from "@/types";

export const Route = createFileRoute("/exceptions")({
  head: () => ({
    meta: [
      { title: "Exceptions — Ledger Control" },
      {
        name: "description",
        content:
          "Review unmatched and low-confidence reconciliation exceptions side by side, inspect AI explanations, then confirm or reject matches.",
      },
      { property: "og:title", content: "Exceptions — Ledger Control" },
      {
        property: "og:description",
        content:
          "Manual resolution workspace for reconciliation exceptions and low-confidence matches.",
      },
    ],
  }),
  component: ExceptionsPage,
});

const PAGE_SIZE = 25;

function ExceptionsPage() {
  const { runId } = useRun();
  const [items, setItems] = useState<LedgerException[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [checked, setChecked] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [page, setPage] = useState(1);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getExceptions(runId);
      setItems(data);
      setChecked(new Set());
    } catch (err) {
      setItems(null);
      setError(err instanceof Error ? err.message : "Could not load exceptions.");
    } finally {
      setLoading(false);
    }
  }, [runId]);

  useEffect(() => {
    void load();
  }, [load]);

  const pageCount = Math.max(1, Math.ceil((items?.length ?? 0) / PAGE_SIZE));
  const currentPage = Math.min(page, pageCount);
  const pageRows = useMemo(
    () => (items ?? []).slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE),
    [items, currentPage],
  );

  const selected = useMemo(
    () => items?.find((i) => i.id === selectedId) ?? null,
    [items, selectedId],
  );

  async function resolve(id: string, action: "confirm" | "reject", candidateId?: string) {
    setBusy(true);
    try {
      await resolveException(id, { action, candidate_id: candidateId });
      toast.success(action === "confirm" ? "Match confirmed" : "Match rejected");
      setSelectedId(null);
      await load();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Resolution failed.");
    } finally {
      setBusy(false);
    }
  }

  async function bulkConfirm() {
    const ids = [...checked];
    if (ids.length === 0) return;
    setBusy(true);
    try {
      for (const id of ids) {
        await resolveException(id, { action: "confirm" });
      }
      toast.success(`Confirmed ${ids.length} exceptions`);
      setChecked(new Set());
      await load();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Bulk resolution failed.");
    } finally {
      setBusy(false);
    }
  }

  function toggleAll() {
    if (checked.size === (items?.length ?? 0)) {
      setChecked(new Set());
    } else {
      setChecked(new Set((items ?? []).map((i) => i.id)));
    }
  }

  function toggleOne(id: string) {
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  // Summary counts
  const totalCount = items?.length ?? 0;
  const highRiskCount =
    items?.filter((i) => (i.confidence ?? 0) < 0.5 && i.status === "exception").length ?? 0;
  const pendingCount = items?.filter((i) => i.status === "pending_review").length ?? 0;
  const openCount = items?.filter((i) => i.status === "exception").length ?? 0;

  return (
    <AppShell
      title="Exception Resolution Queue"
      description="Isolated ledger discrepancies, break isolation, AI-assisted diagnostics, and dual-party confirmation."
    >
      <div className="space-y-4">
        {/* Exception KPI Strip */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div className="p-3.5 rounded-[6px] bg-[var(--lc-surface)] border border-[var(--lc-border)] shadow-sm">
            <div className="flex items-center justify-between">
              <span className="label-micro text-[var(--lc-text-muted)]">Total Discrepancies</span>
              <AlertTriangle className="size-4 text-[var(--lc-accent)]" />
            </div>
            <p className="num mt-2 text-xl font-bold font-mono text-[var(--lc-text-primary)]">
              {totalCount}
            </p>
          </div>

          <div className="p-3.5 rounded-[6px] bg-[var(--lc-surface)] border border-[var(--lc-border)] shadow-sm">
            <div className="flex items-center justify-between">
              <span className="label-micro text-[var(--lc-text-muted)]">Open Exceptions</span>
              <span className="size-2 rounded-full bg-[var(--lc-danger)] shadow-[0_0_6px_var(--lc-danger)]" />
            </div>
            <p className="num mt-2 text-xl font-bold font-mono text-[var(--lc-danger)]">
              {openCount}
            </p>
          </div>

          <div className="p-3.5 rounded-[6px] bg-[var(--lc-surface)] border border-[var(--lc-border)] shadow-sm">
            <div className="flex items-center justify-between">
              <span className="label-micro text-[var(--lc-text-muted)]">Pending Review</span>
              <Clock className="size-4 text-[var(--lc-warning)]" />
            </div>
            <p className="num mt-2 text-xl font-bold font-mono text-[var(--lc-warning)]">
              {pendingCount}
            </p>
          </div>

          <div className="p-3.5 rounded-[6px] bg-[var(--lc-surface)] border border-[var(--lc-border)] shadow-sm">
            <div className="flex items-center justify-between">
              <span className="label-micro text-[var(--lc-text-muted)]">High Risk Breaks</span>
              <span className="size-2 rounded-full bg-[var(--lc-danger)] shadow-[0_0_6px_var(--lc-danger)]" />
            </div>
            <p className="num mt-2 text-xl font-bold font-mono text-[var(--lc-danger)]">
              {highRiskCount}
            </p>
          </div>
        </div>

        <AiInsightsPanel
          runId={runId}
          onView={(ins) => {
            if (ins.exception_id) setSelectedId(ins.exception_id);
          }}
        />

        <Panel
          title="Exception Queue"
          subtitle={
            runId
              ? `run_id ${runId} · ${items?.length ?? 0} exceptions`
              : "All active exceptions across reconciliation runs"
          }
          actions={
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => void load()}
                aria-label="Refresh exceptions"
                className="lc-btn lc-btn--secondary text-xs"
              >
                <RefreshCw className="size-3.5" aria-hidden />
                Refresh
              </button>

              <Can permission="reconciliation.resolve">
                {checked.size > 0 ? (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void bulkConfirm()}
                    className="lc-btn lc-btn--success text-xs"
                  >
                    <Check className="size-3.5" aria-hidden />
                    Confirm Selected ({checked.size})
                  </button>
                ) : null}
              </Can>
            </div>
          }
        >
          {loading ? (
            <LoadingState label="Loading exceptions" />
          ) : error ? (
            <ErrorState message={error} onRetry={() => void load()} />
          ) : !items || items.length === 0 ? (
            <EmptyState
              title="Exception queue clear"
              description="No unresolved exceptions or reconciliation breaks found."
            />
          ) : (
            <>
              <div className="overflow-x-auto rounded-[6px] border-t border-[var(--lc-border)] bg-[var(--lc-surface)]">
                <table className="w-full min-w-[900px] border-collapse text-sm">
                  <caption className="sr-only">Exceptions list</caption>
                  <thead>
                    <tr className="border-b border-[var(--lc-border)] bg-[var(--lc-surface-elevated)]">
                      <th className="w-10 px-3 py-2.5 text-center">
                        <input
                          type="checkbox"
                          aria-label="Select all"
                          checked={checked.size === items.length && items.length > 0}
                          onChange={toggleAll}
                          className="rounded border-[var(--lc-border-strong)] bg-[var(--lc-surface)] accent-[var(--lc-accent)]"
                        />
                      </th>
                      {[
                        "Date",
                        "Statement Description",
                        "Amount",
                        "Candidate Ledger Match",
                        "Confidence",
                        "Status",
                        "",
                      ].map((h, i) => (
                        <th
                          key={i}
                          className={cn(
                            "label-micro px-3.5 py-2.5 text-left font-semibold text-[var(--lc-text-muted)]",
                            i === 2 && "text-right",
                          )}
                        >
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--lc-border-subtle)]">
                    {pageRows.map((ex) => {
                      const stmt = ex.statement_side;
                      const cand = ex.ledger_side;
                      const isChecked = checked.has(ex.id);
                      return (
                        <tr
                          key={ex.id}
                          className={cn(
                            "cursor-pointer transition-colors hover:bg-[rgba(168,85,247,0.04)]",
                            isChecked && "bg-[var(--lc-accent-soft)]",
                          )}
                          onClick={() => setSelectedId(ex.id)}
                        >
                          <td
                            className="px-3 py-2.5 text-center"
                            onClick={(e) => {
                              e.stopPropagation();
                              toggleOne(ex.id);
                            }}
                          >
                            <input
                              type="checkbox"
                              aria-label={`Select ${ex.id}`}
                              checked={isChecked}
                              onChange={() => toggleOne(ex.id)}
                              className="rounded border-[var(--ledger-border-strong)] bg-[var(--ledger-surface)] accent-[var(--ledger-primary)]"
                            />
                          </td>
                          <td className="num px-3.5 py-2.5 whitespace-nowrap text-xs font-mono text-[var(--ledger-text-secondary)]">
                            {formatDate(stmt?.date ?? ex.date)}
                          </td>
                          <td className="max-w-[280px] px-3.5 py-2.5">
                            <span
                              className="block truncate font-medium text-[var(--ledger-text)]"
                              title={stmt?.description}
                            >
                              {stmt?.description ?? "Statement record"}
                            </span>
                          </td>
                          <td className="num px-3.5 py-2.5 whitespace-nowrap text-right text-xs font-mono font-bold text-[var(--ledger-text)]">
                            {formatMoney(stmt?.amount ?? null)}
                          </td>
                          <td className="max-w-[240px] px-3.5 py-2.5">
                            {cand ? (
                              <span
                                className="block truncate text-xs text-[var(--ledger-text-secondary)] font-mono"
                                title={cand.description}
                              >
                                {cand.description}
                              </span>
                            ) : (
                              <span className="text-xs text-[var(--ledger-text-faint)] italic">
                                No candidate match
                              </span>
                            )}
                          </td>
                          <td className="px-3.5 py-2.5 whitespace-nowrap">
                            <ConfidenceBar confidence={ex.confidence} />
                          </td>
                          <td className="px-3.5 py-2.5 whitespace-nowrap">
                            <StatusChip status={ex.status} />
                          </td>
                          <td
                            className="px-3.5 py-2.5 whitespace-nowrap text-right"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <button
                              type="button"
                              onClick={() => setSelectedId(ex.id)}
                              className="lc-btn lc-btn--ghost text-xs py-1 px-2 text-[var(--ledger-primary)]"
                            >
                              Review
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

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

      <ExceptionDrawer
        exception={selected}
        busy={busy}
        onClose={() => setSelectedId(null)}
        onResolve={(action) => {
          if (selected) {
            const candidateId = selected.ledger_side?.id || undefined;
            void resolve(selected.id, action, candidateId);
          }
        }}
      />
    </AppShell>
  );
}
