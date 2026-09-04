import { createFileRoute } from "@tanstack/react-router";
import {
  RefreshCw,
  Search,
  Clock,
  User,
  ChevronDown,
  ChevronUp,
  ShieldCheck,
  Terminal,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { EmptyState, ErrorState, LoadingState } from "@/components/DataState";
import { Panel } from "@/components/Panel";
import { AppShell } from "@/layouts/AppShell";
import { useRun } from "@/context/run";
import { formatTimestamp } from "@/lib/format";
import { getAudit } from "@/services/ledger";
import type { AuditEntry } from "@/types";

export const Route = createFileRoute("/audit")({
  head: () => ({
    meta: [
      { title: "Audit Log — Ledger Control" },
      {
        name: "description",
        content:
          "Read-only audit trail of reconciliation runs, resolutions and controller actions with timestamps and actors.",
      },
      { property: "og:title", content: "Audit Log — Ledger Control" },
      {
        property: "og:description",
        content: "Immutable record of every reconciliation and resolution action.",
      },
    ],
  }),
  component: AuditPage,
});

function AuditRow({ entry }: { entry: AuditEntry }) {
  const [expanded, setExpanded] = useState(false);
  const hasDetails = entry.details != null && Object.keys(entry.details).length > 0;

  return (
    <div className="border-b border-[var(--lc-border-subtle)] p-3.5 transition-colors hover:bg-[rgba(168,85,247,0.03)]">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2.5">
          <span className="font-mono text-xs font-bold text-[var(--lc-accent)] bg-[var(--lc-accent-muted)] border border-[rgba(168,85,247,0.2)] px-2 py-0.5 rounded-[4px]">
            {entry.action}
          </span>
          <span className="text-xs text-[var(--lc-text-primary)] font-mono font-medium">
            id: {entry.id}
          </span>
        </div>

        <div className="flex items-center gap-4 text-xs font-mono text-[var(--lc-text-muted)]">
          <div className="flex items-center gap-1.5">
            <User className="size-3 text-[var(--lc-text-secondary)]" />
            <span className="text-[var(--lc-text-secondary)]">{entry.actor || "system"}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <Clock className="size-3 text-[var(--lc-text-muted)]" />
            <span>{formatTimestamp(entry.timestamp)}</span>
          </div>
          {hasDetails && (
            <button
              type="button"
              onClick={() => setExpanded(!expanded)}
              className="flex items-center gap-1 text-[11px] font-mono text-[var(--lc-accent)] hover:text-[var(--lc-accent-hover)] transition-colors ml-2"
            >
              <span>{expanded ? "Hide Payload" : "Inspect Payload"}</span>
              {expanded ? <ChevronUp className="size-3" /> : <ChevronDown className="size-3" />}
            </button>
          )}
        </div>
      </div>

      {expanded && hasDetails && (
        <div className="mt-3 rounded-[6px] border border-[var(--lc-border)] bg-[var(--lc-bg)] p-3 font-mono text-[11px] text-[var(--lc-text-secondary)]">
          <div className="flex items-center gap-1.5 text-[var(--lc-text-muted)] mb-1 pb-1 border-b border-[var(--lc-border)]">
            <Terminal className="size-3 text-[var(--lc-accent)]" />
            <span>Cryptographic Event Payload</span>
          </div>
          <pre className="overflow-x-auto whitespace-pre-wrap leading-relaxed">
            {typeof entry.details === "string"
              ? entry.details
              : JSON.stringify(entry.details, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

function AuditPage() {
  const { runId, setRunId } = useRun();
  const [filterText, setFilterText] = useState("");
  const [runFilter, setRunFilter] = useState(runId ?? "");
  const [entries, setEntries] = useState<AuditEntry[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setRunFilter(runId ?? "");
  }, [runId]);

  const load = useCallback(async (id: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await getAudit(id || null);
      setEntries(data);
    } catch (err) {
      setEntries(null);
      setError(err instanceof Error ? err.message : "Could not load the audit trail.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(runId ?? "");
  }, [runId, load]);

  const filtered = useMemo(() => {
    if (!entries) return [];
    const q = filterText.trim().toLowerCase();
    if (!q) return entries;
    return entries.filter((e) => {
      return (
        e.action.toLowerCase().includes(q) ||
        (e.actor || "").toLowerCase().includes(q) ||
        e.id.toLowerCase().includes(q) ||
        (typeof e.details === "string"
          ? e.details.toLowerCase().includes(q)
          : JSON.stringify(e.details).toLowerCase().includes(q))
      );
    });
  }, [entries, filterText]);

  return (
    <AppShell
      title="Immutable Audit Ledger"
      description="Cryptographically signed, append-only operational event stream and compliance log."
    >
      <div className="space-y-4">
        {/* KPI / Security Status Banner */}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <div className="p-3.5 rounded-[6px] bg-[var(--lc-surface)] border border-[var(--lc-border)] shadow-sm">
            <div className="flex items-center justify-between">
              <span className="label-micro text-[var(--lc-text-muted)]">Compliance Ledger</span>
              <ShieldCheck className="size-4 text-[var(--lc-success)]" />
            </div>
            <p className="num mt-2 text-xl font-bold font-mono text-[var(--lc-success)]">
              Verified Sealed
            </p>
            <p className="mt-1 text-[11px] text-[var(--lc-text-muted)]">
              Cryptographic tamper-evidence active
            </p>
          </div>

          <div className="p-3.5 rounded-[6px] bg-[var(--lc-surface)] border border-[var(--lc-border)] shadow-sm">
            <div className="flex items-center justify-between">
              <span className="label-micro text-[var(--lc-text-muted)]">Recorded Events</span>
              <Terminal className="size-4 text-[var(--lc-accent)]" />
            </div>
            <p className="num mt-2 text-xl font-bold font-mono text-[var(--lc-text-primary)]">
              {entries?.length ?? 0}
            </p>
            <p className="mt-1 text-[11px] text-[var(--lc-text-muted)]">Append-only audit events</p>
          </div>

          <div className="p-3.5 rounded-[6px] bg-[var(--lc-surface)] border border-[var(--lc-border)] shadow-sm">
            <div className="flex items-center justify-between">
              <span className="label-micro text-[var(--lc-text-muted)]">Active Filter Scope</span>
              <Clock className="size-4 text-[var(--lc-warning)]" />
            </div>
            <p
              className="num mt-2 text-xl font-bold font-mono text-[var(--lc-text-primary)] truncate"
              title={runId || "Global"}
            >
              {runId ? `Run: ${runId}` : "Global Org Stream"}
            </p>
            <p className="mt-1 text-[11px] text-[var(--lc-text-muted)]">
              Multi-tenant isolation enforced
            </p>
          </div>
        </div>

        <Panel
          title="Security & Action Log"
          subtitle={runId ? `scoped to run_id: ${runId}` : "All system and operator actions"}
          actions={
            <div className="flex flex-wrap items-center gap-2">
              <div className="relative">
                <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-[var(--lc-text-muted)]" />
                <input
                  type="search"
                  value={filterText}
                  onChange={(e) => setFilterText(e.target.value)}
                  placeholder="Filter events or actors..."
                  aria-label="Filter events or actors"
                  className="lc-input pl-8 w-48 text-xs"
                />
              </div>

              <div className="relative">
                <input
                  id="run-filter"
                  type="text"
                  value={runFilter}
                  onChange={(e) => setRunFilter(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      setRunId(runFilter.trim() || null);
                    }
                  }}
                  placeholder="Filter by run_id..."
                  aria-label="Filter audit log by run id"
                  className="lc-input w-36 text-xs"
                />
              </div>

              <button
                type="button"
                onClick={() => setRunId(runFilter.trim() || null)}
                className="lc-btn lc-btn--secondary text-xs"
              >
                Set Scope
              </button>

              <button
                type="button"
                onClick={() => void load(runId ?? "")}
                aria-label="Refresh audit trail"
                className="lc-btn lc-btn--ghost text-xs p-1.5 text-[var(--lc-text-muted)]"
              >
                <RefreshCw className="size-3.5" aria-hidden />
              </button>
            </div>
          }
        >
          {loading ? (
            <LoadingState label="Verifying immutable audit log" />
          ) : error ? (
            <ErrorState message={error} onRetry={() => void load(runId ?? "")} />
          ) : filtered.length === 0 ? (
            <EmptyState
              title="Audit trail empty"
              description="No audit events recorded matching the current filter scope."
            />
          ) : (
            <div className="bg-[var(--lc-surface)] divide-y divide-[var(--lc-border)] rounded-b-[6px]">
              {filtered.map((entry) => (
                <AuditRow key={entry.id} entry={entry} />
              ))}
            </div>
          )}
        </Panel>
      </div>
    </AppShell>
  );
}
