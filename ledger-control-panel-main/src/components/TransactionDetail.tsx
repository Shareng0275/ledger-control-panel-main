import { X } from "lucide-react";
import { useEffect } from "react";

import { ConfidenceBar } from "@/components/ConfidenceBar";
import { StatusChip } from "@/components/StatusChip";
import { formatDate, formatMoney } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Transaction } from "@/types";

function Row({ k, v, mono }: { k: string; v: string; mono?: boolean }) {
  return (
    <div className="flex items-start justify-between gap-3 py-1">
      <dt className="label-micro shrink-0 text-[var(--ledger-text-muted)]">{k}</dt>
      <dd
        className={cn(
          "truncate text-right text-xs text-[var(--ledger-text)]",
          mono && "num font-mono",
        )}
        title={v}
      >
        {v}
      </dd>
    </div>
  );
}

export function TransactionDetail({
  transaction,
  onClose,
}: {
  transaction: Transaction | null;
  onClose: () => void;
}) {
  useEffect(() => {
    if (!transaction) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [transaction, onClose]);

  if (!transaction) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <button
        type="button"
        aria-label="Close transaction details"
        onClick={onClose}
        className="lc-drawer-backdrop absolute inset-0 bg-black/70 backdrop-blur-[2px]"
      />
      <aside
        role="dialog"
        aria-label="Transaction details"
        className="lc-drawer-panel relative flex h-full w-full max-w-md flex-col border-l border-[var(--ledger-border)] bg-[var(--ledger-surface)] shadow-2xl"
      >
        <header className="flex items-start justify-between gap-3 border-b border-[var(--ledger-border)] px-4 py-3.5 bg-[var(--ledger-surface-elevated)]">
          <div className="min-w-0">
            <p className="label-micro text-[var(--ledger-text-muted)]">Transaction Detail</p>
            <p className="num mt-0.5 truncate text-xs font-mono font-bold text-[var(--ledger-primary)]">
              {transaction.id}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-[4px] border border-[var(--ledger-border)] p-1 text-[var(--ledger-text-muted)] transition-colors hover:bg-[var(--ledger-surface-hover)] hover:text-[var(--ledger-text)]"
            aria-label="Close"
          >
            <X className="size-4" aria-hidden />
          </button>
        </header>

        <div className="flex-1 space-y-4 overflow-y-auto p-4">
          <div className="rounded-[4px] border border-[var(--ledger-border)] bg-[var(--ledger-surface-elevated)] p-3">
            <div className="flex items-center justify-between">
              <StatusChip status={transaction.status} />
              <div className="text-right">
                <p className="num text-base font-bold font-mono text-[var(--ledger-text)]">
                  {formatMoney(transaction.amount, transaction.currency)}
                </p>
              </div>
            </div>
            <p className="mt-2 text-xs font-medium text-[var(--ledger-text)]">
              {transaction.description}
            </p>
          </div>

          <div className="rounded-[4px] border border-[var(--ledger-border)] bg-[var(--ledger-surface)] p-3">
            <p className="label-micro text-[var(--ledger-text-muted)] mb-2">Metadata</p>
            <dl className="divide-y divide-[var(--ledger-border-subtle)] space-y-1 text-xs">
              <Row k="Date" v={formatDate(transaction.date)} />
              <Row k="Source" v={transaction.source} mono />
              <Row k="External Ref" v={transaction.external_ref ?? "—"} mono />
              {transaction.match_id ? <Row k="Match ID" v={transaction.match_id} mono /> : null}
            </dl>
          </div>

          <div className="rounded-[4px] border border-[var(--ledger-border)] bg-[var(--ledger-surface)] p-3">
            <p className="label-micro text-[var(--ledger-text-muted)] mb-2">Matching Confidence</p>
            <div className="flex items-center justify-between">
              <ConfidenceBar confidence={transaction.confidence} width="w-32" />
            </div>
          </div>
        </div>

        <footer className="border-t border-[var(--ledger-border)] p-3 bg-[var(--ledger-surface-elevated)]">
          <button
            type="button"
            onClick={onClose}
            className="lc-btn lc-btn--secondary w-full text-xs"
          >
            Close Details
          </button>
        </footer>
      </aside>
    </div>
  );
}
