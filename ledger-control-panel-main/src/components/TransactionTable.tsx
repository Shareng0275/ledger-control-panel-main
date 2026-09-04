import React, { useEffect, useRef } from "react";

import { ConfidenceBar } from "@/components/ConfidenceBar";
import { StatusChip } from "@/components/StatusChip";
import { formatDate, formatMoney } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Transaction } from "@/types";

export const TransactionTable = React.memo(function TransactionTable({
  rows,
  activeIndex = -1,
  onActiveIndexChange,
  onOpen,
}: {
  rows: Transaction[];
  activeIndex?: number;
  onActiveIndexChange?: (index: number) => void;
  onOpen?: (tx: Transaction) => void;
}) {
  const bodyRef = useRef<HTMLTableSectionElement>(null);

  // Keep the keyboard-active row in view.
  useEffect(() => {
    if (activeIndex < 0) return;
    const el = bodyRef.current?.querySelector<HTMLElement>(`[data-index="${activeIndex}"]`);
    el?.scrollIntoView({ block: "nearest" });
  }, [activeIndex]);

  function handleKeyDown(e: React.KeyboardEvent<HTMLTableSectionElement>) {
    if (!rows.length) return;
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      const delta = e.key === "ArrowDown" ? 1 : -1;
      const next = Math.max(
        0,
        Math.min(rows.length - 1, (activeIndex < 0 ? 0 : activeIndex) + delta),
      );
      onActiveIndexChange?.(next);
      return;
    }
    if (e.key === "Enter" || e.key === " ") {
      const tx = rows[activeIndex];
      if (tx) {
        e.preventDefault();
        onOpen?.(tx);
      }
    }
  }

  return (
    <div className="overflow-x-auto rounded-[6px] border border-[var(--lc-border)] bg-[var(--lc-surface)] shadow-sm">
      <table className="w-full min-w-[860px] border-collapse text-sm">
        <caption className="sr-only">
          Reconciled transactions. Use arrow keys to move between rows and Enter to open details.
        </caption>
        <thead>
          <tr className="border-b border-[var(--lc-border)] bg-[var(--lc-surface-elevated)]">
            {["Date", "Description", "Amount", "Source", "Confidence", "Status"].map((h, i) => (
              <th
                key={h}
                className={cn(
                  "label-micro px-3.5 py-2.5 text-left font-semibold text-[var(--lc-text-muted)]",
                  (i === 2 || i === 4) && "text-right",
                )}
              >
                <span className={cn(i === 2 && "block text-right", i === 4 && "block text-right")}>
                  {h}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody
          ref={bodyRef}
          tabIndex={0}
          onKeyDown={handleKeyDown}
          className="divide-y divide-[var(--lc-border-subtle)] outline-none focus-visible:ring-1 focus-visible:ring-[var(--lc-accent)]"
        >
          {rows.map((t, i) => (
            <tr
              key={t.id}
              data-index={i}
              aria-selected={i === activeIndex}
              onClick={() => {
                onActiveIndexChange?.(i);
                onOpen?.(t);
              }}
              className={cn(
                "cursor-pointer transition-colors hover:bg-[rgba(168,85,247,0.04)]",
                i === activeIndex &&
                  "bg-[var(--lc-accent-soft)] ring-1 ring-inset ring-[rgba(168,85,247,0.3)]",
              )}
            >
              <td className="num px-3.5 py-2.5 whitespace-nowrap text-xs font-mono text-[var(--lc-text-secondary)]">
                {formatDate(t.date)}
              </td>
              <td className="max-w-[360px] px-3.5 py-2.5">
                <span
                  className="block truncate font-medium text-[var(--lc-text-primary)]"
                  title={t.description}
                >
                  {t.description}
                </span>
              </td>
              <td className="num px-3.5 py-2.5 whitespace-nowrap text-right text-xs font-mono font-bold text-[var(--lc-text-primary)]">
                {formatMoney(t.amount, t.currency)}
              </td>
              <td className="px-3.5 py-2.5 whitespace-nowrap text-xs font-mono text-[var(--lc-text-muted)]">
                <span className="rounded-[3px] bg-[var(--lc-surface-elevated)] border border-[var(--lc-border)] px-1.5 py-0.5 text-[10px]">
                  {t.source}
                </span>
              </td>
              <td className="px-3.5 py-2.5 whitespace-nowrap text-right">
                <div className="inline-flex justify-end">
                  <ConfidenceBar confidence={t.confidence} />
                </div>
              </td>
              <td className="px-3.5 py-2.5 whitespace-nowrap">
                <StatusChip status={t.status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
});
