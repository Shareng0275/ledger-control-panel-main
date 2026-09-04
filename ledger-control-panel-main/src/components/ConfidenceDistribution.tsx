import { confidencePct } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Transaction } from "@/types";

const BUCKETS = [
  { label: "0–34", min: 0, max: 34, bar: "bg-[#EF4444]", text: "text-[#EF4444]" },
  { label: "35–59", min: 35, max: 59, bar: "bg-[#F59E0B]", text: "text-[#F59E0B]" },
  { label: "60–84", min: 60, max: 84, bar: "bg-[#60A5FA]", text: "text-[#60A5FA]" },
  { label: "85–100", min: 85, max: 100, bar: "bg-[#22C55E]", text: "text-[#22C55E]" },
] as const;

/** Distribution of backend-scored match confidence across the current run's rows. */
export function ConfidenceDistribution({ rows }: { rows: Transaction[] }) {
  const scored = rows
    .map((r) => confidencePct(r.confidence))
    .filter((p): p is number => p !== null);
  const unscored = rows.length - scored.length;

  const counts = BUCKETS.map((b) => scored.filter((p) => p >= b.min && p <= b.max).length);
  const max = Math.max(1, ...counts);

  return (
    <div className="px-4 py-4 bg-[var(--ledger-surface)] rounded-[4px] border border-[var(--ledger-border)] shadow-sm">
      <div className="grid grid-cols-4 items-end gap-3">
        {BUCKETS.map((b, i) => {
          const count = counts[i] ?? 0;
          return (
            <div key={b.label} className="flex flex-col items-stretch gap-1.5">
              <p className={cn("num text-right text-xs font-mono font-bold", b.text)}>{count}</p>
              <div className="flex h-24 items-end border-b border-[var(--ledger-border)] bg-[var(--ledger-surface-elevated)] rounded-t-[3px]">
                <div
                  className={cn("w-full transition-all duration-300 rounded-t-[3px]", b.bar)}
                  style={{ height: `${(count / max) * 100}%` }}
                  aria-hidden
                />
              </div>
              <p className="label-micro text-center text-[var(--ledger-text-muted)] text-[10px]">
                {b.label}%
              </p>
            </div>
          );
        })}
      </div>
      <p className="mt-3 border-t border-[var(--ledger-border)] pt-2 text-[11px] font-mono text-[var(--ledger-text-muted)]">
        <span className="num font-semibold text-[var(--ledger-text)]">{scored.length}</span> scored
        records
        {unscored > 0 ? (
          <>
            {" · "}
            <span className="num text-[var(--ledger-text-faint)]">{unscored}</span> unscored
          </>
        ) : null}
      </p>
    </div>
  );
}
