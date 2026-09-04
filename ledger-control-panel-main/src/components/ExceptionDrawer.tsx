import { Check, Sparkles, X, AlertTriangle } from "lucide-react";
import { useEffect, useState } from "react";

import { ConfidenceBar } from "@/components/ConfidenceBar";
import { StatusChip } from "@/components/StatusChip";
import { formatDate, formatMoney } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { ExceptionCandidate, LedgerException } from "@/types";

function Row({ k, v, mono }: { k: string; v: string; mono?: boolean }) {
  return (
    <div className="flex items-start justify-between gap-3 py-1">
      <dt className="label-micro shrink-0 text-[var(--lc-text-muted)]">{k}</dt>
      <dd
        className={cn(
          "truncate text-right text-xs text-[var(--lc-text-primary)]",
          mono && "num font-mono",
        )}
        title={v}
      >
        {v}
      </dd>
    </div>
  );
}

function SideCard({
  label,
  side,
  tone,
}: {
  label: string;
  side: ExceptionCandidate | null;
  tone: "verify" | "accent";
}) {
  return (
    <div className="p-3.5 rounded-[6px] border border-[var(--lc-border)] bg-[var(--lc-surface-elevated)]">
      <p
        className={cn(
          "label-micro font-bold",
          tone === "accent" ? "text-[var(--lc-accent)]" : "text-[var(--lc-success)]",
        )}
      >
        {label}
      </p>
      {!side ? (
        <p className="mt-2 text-xs text-[var(--lc-text-muted)] italic">
          No record supplied by backend.
        </p>
      ) : (
        <dl className="mt-2 space-y-1 text-xs divide-y divide-[var(--lc-border-subtle)]">
          <Row k="Date" v={formatDate(side.date)} />
          <Row k="Description" v={side.description ?? "—"} />
          <Row k="Amount" v={formatMoney(side.amount ?? null)} mono />
          <Row k="Source" v={side.source ?? "—"} mono />
          {side.id ? <Row k="Ref" v={side.id} mono /> : null}
        </dl>
      )}
    </div>
  );
}

/** Manual review drawer: statement vs ledger comparison, AI explanation, resolution actions. */
export function ExceptionDrawer({
  exception,
  busy,
  onClose,
  onResolve,
}: {
  exception: LedgerException | null;
  busy: boolean;
  onClose: () => void;
  onResolve: (action: "confirm" | "reject") => void;
}) {
  const [confirmingAction, setConfirmingAction] = useState<"confirm" | "reject" | null>(null);

  useEffect(() => {
    setConfirmingAction(null);
  }, [exception]);

  useEffect(() => {
    if (!exception) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [exception, onClose]);

  if (!exception) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <button
        type="button"
        aria-label="Close manual review"
        onClick={onClose}
        className="lc-drawer-backdrop absolute inset-0 bg-black/75 backdrop-blur-[3px]"
      />
      <aside
        role="dialog"
        aria-label="Exception manual review"
        className="lc-drawer-panel relative flex h-full w-full max-w-lg flex-col border-l border-[var(--lc-border)] bg-[var(--lc-surface)] shadow-2xl"
      >
        <header className="flex items-start justify-between gap-3 border-b border-[var(--lc-border)] px-4 py-3.5 bg-[var(--lc-surface-elevated)]">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="label-micro text-[var(--lc-text-muted)]">Exception Review</span>
              <StatusChip status={exception.status} />
            </div>
            <p className="num mt-1 truncate text-xs font-mono font-bold text-[var(--lc-accent)]">
              {exception.id}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-[4px] border border-[var(--lc-border)] p-1 text-[var(--lc-text-muted)] transition-colors hover:bg-[var(--lc-surface-hover)] hover:text-[var(--lc-text-primary)]"
            aria-label="Close"
          >
            <X className="size-4" aria-hidden />
          </button>
        </header>

        <div className="flex-1 space-y-4 overflow-y-auto p-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <SideCard
              label="Bank Statement Record"
              side={exception.statement_side ?? null}
              tone="verify"
            />
            <SideCard
              label="Gateway Ledger Candidate"
              side={exception.ledger_side ?? null}
              tone="accent"
            />
          </div>

          {exception.confidence != null && (
            <div className="rounded-[6px] border border-[var(--lc-border)] bg-[var(--lc-surface-elevated)] p-3.5">
              <p className="label-micro text-[var(--lc-text-muted)] mb-2">
                Match Confidence Assessment
              </p>
              <ConfidenceBar confidence={exception.confidence} width="w-full" showLabel />
            </div>
          )}

          {exception.reason && (
            <div className="rounded-[6px] border border-[rgba(168,85,247,0.25)] bg-[var(--lc-accent-muted)] p-3.5">
              <div className="flex items-center gap-2 text-[var(--lc-accent)] mb-1.5">
                <Sparkles className="size-4" />
                <span className="font-display text-xs font-bold">AI Diagnostics & Explanation</span>
              </div>
              <p className="text-xs text-[var(--lc-text-primary)] leading-relaxed">
                {exception.reason}
              </p>
            </div>
          )}

          {confirmingAction && (
            <div className="rounded-[6px] border border-[rgba(245,158,11,0.3)] bg-[rgba(245,158,11,0.06)] p-3.5">
              <div className="flex items-center gap-2 text-[var(--lc-warning)]">
                <AlertTriangle className="size-4 shrink-0" />
                <p className="font-display text-xs font-bold">
                  {confirmingAction === "confirm"
                    ? "Confirm Valid Reconciliation Match?"
                    : "Reject & Isolate Break?"}
                </p>
              </div>
              <p className="mt-1 text-xs text-[var(--lc-text-secondary)]">
                {confirmingAction === "confirm"
                  ? "This record will be reconciled and sealed in the immutable compliance audit ledger."
                  : "This discrepancy will be flagged as permanently unmatched in the system."}
              </p>
              <div className="mt-3 flex items-center gap-2">
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => onResolve(confirmingAction)}
                  className={cn(
                    "lc-btn text-xs",
                    confirmingAction === "confirm" ? "lc-btn--success" : "lc-btn--danger",
                  )}
                >
                  <Check className="size-3.5" />
                  {confirmingAction === "confirm" ? "Yes, Confirm Match" : "Yes, Reject Break"}
                </button>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => setConfirmingAction(null)}
                  className="lc-btn lc-btn--ghost text-xs"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>

        <footer className="border-t border-[var(--lc-border)] p-3.5 bg-[var(--lc-surface-elevated)] flex items-center justify-end gap-2.5">
          <button
            type="button"
            disabled={busy || confirmingAction !== null}
            onClick={() => setConfirmingAction("reject")}
            className="lc-btn lc-btn--danger text-xs"
          >
            Reject Match
          </button>
          <button
            type="button"
            disabled={busy || confirmingAction !== null}
            onClick={() => setConfirmingAction("confirm")}
            className="lc-btn lc-btn--success text-xs"
          >
            <Check className="size-3.5" />
            Confirm Match
          </button>
        </footer>
      </aside>
    </div>
  );
}
