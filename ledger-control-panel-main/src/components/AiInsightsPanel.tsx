import { ChevronDown, ChevronUp, RefreshCw, Sparkles } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { EmptyState, ErrorState, LoadingState } from "@/components/DataState";
import { Panel } from "@/components/Panel";
import { cn } from "@/lib/utils";
import { getInsights } from "@/services/ledger";
import type { RunInsight } from "@/types";

/** Collapsible panel rendering AI insights returned by the backend for the active run. */
export function AiInsightsPanel({
  runId,
  onView,
}: {
  runId?: string | null;
  onView?: (insight: RunInsight) => void;
}) {
  const [open, setOpen] = useState(true);
  const [items, setItems] = useState<RunInsight[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setItems(await getInsights(runId));
    } catch (err) {
      setItems(null);
      setError(err instanceof Error ? err.message : "Could not load AI insights.");
    } finally {
      setLoading(false);
    }
  }, [runId]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <Panel
      title="AI Operational Diagnostics"
      subtitle={runId ? `run_id ${runId}` : "Latest backend reconciliation state"}
      actions={
        <>
          <button
            type="button"
            onClick={() => void load()}
            aria-label="Reload AI insights"
            className="lc-btn lc-btn--ghost text-xs py-1 px-2 text-[var(--ledger-text-muted)]"
          >
            <RefreshCw className="size-3.5" aria-hidden />
          </button>
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
            className="lc-btn lc-btn--secondary text-xs py-1 px-2.5"
          >
            {open ? (
              <ChevronUp className="size-3.5" aria-hidden />
            ) : (
              <ChevronDown className="size-3.5" aria-hidden />
            )}
            {open ? "Collapse" : "Expand"}
          </button>
        </>
      }
    >
      {!open ? null : loading ? (
        <LoadingState label="Loading AI diagnostics" />
      ) : error ? (
        <ErrorState message={error} onRetry={() => void load()} />
      ) : !items || items.length === 0 ? (
        <EmptyState
          title="No anomalies detected"
          description="The backend AI engine identified no risk alerts for this reconciliation state."
        />
      ) : (
        <ul className="divide-y divide-[var(--ledger-border)]">
          {items.map((ins, idx) => (
            <li
              key={ins.id ?? `${ins.type}-${idx}`}
              className="flex items-start gap-3 px-4 py-3 hover:bg-[var(--ledger-surface-hover)] transition-colors"
            >
              <Sparkles
                className={cn(
                  "mt-0.5 size-4 shrink-0",
                  ins.severity === "high"
                    ? "text-[#D65C68]"
                    : ins.severity === "medium"
                      ? "text-[#D7A94A]"
                      : "text-[var(--ledger-primary)]",
                )}
                aria-hidden
              />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="num text-[10px] tracking-wide text-[var(--ledger-text-muted)] uppercase font-mono">
                    {ins.type}
                  </span>
                  {ins.severity ? (
                    <span
                      className={cn(
                        "rounded-[3px] border px-1.5 py-0.5 text-[9px] uppercase font-mono font-bold",
                        ins.severity === "high"
                          ? "border-[rgba(214,92,104,0.3)] bg-[rgba(214,92,104,0.12)] text-[#D65C68]"
                          : ins.severity === "medium"
                            ? "border-[rgba(215,169,74,0.3)] bg-[rgba(215,169,74,0.12)] text-[#D7A94A]"
                            : "border-[var(--ledger-border)] bg-[var(--ledger-surface-elevated)] text-[var(--ledger-text-muted)]",
                      )}
                    >
                      {ins.severity}
                    </span>
                  ) : null}
                </div>
                {ins.title ? (
                  <p className="mt-1 font-display text-xs font-semibold text-[var(--ledger-text)]">
                    {ins.title}
                  </p>
                ) : null}
                <p className="mt-1 text-xs leading-relaxed text-[var(--ledger-text-muted)]">
                  {ins.message}
                </p>
              </div>
              {onView && (ins.exception_id || ins.transaction_id) ? (
                <button
                  type="button"
                  onClick={() => onView(ins)}
                  className="lc-btn lc-btn--ghost text-xs py-1 px-2 text-[var(--ledger-primary)] shrink-0"
                >
                  Inspect
                </button>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
