import React from "react";
import { cn } from "@/lib/utils";
import { confidencePct } from "@/lib/format";

interface Props {
  confidence?: number | null | undefined;
  value?: number | null | undefined;
  className?: string;
  width?: string;
  showLabel?: boolean;
}

function tone(pct: number) {
  if (pct >= 85) return { bar: "bg-[#22C55E]", text: "text-[#22C55E]", label: "High" };
  if (pct >= 60) return { bar: "bg-[#60A5FA]", text: "text-[#60A5FA]", label: "Med" };
  if (pct >= 35) return { bar: "bg-[#F59E0B]", text: "text-[#F59E0B]", label: "Fair" };
  return { bar: "bg-[#EF4444]", text: "text-[#EF4444]", label: "Low" };
}

/** Confidence representation: percentage + static progress indicator + semantic label. */
export const ConfidenceBar = React.memo(function ConfidenceBar({
  confidence,
  value,
  className,
  width = "w-16",
  showLabel = true,
}: Props) {
  const confVal = confidence !== undefined ? confidence : value;
  const pct = confidencePct(confVal);

  if (pct === null) {
    return (
      <div className={cn("flex items-center gap-1.5", className)}>
        <div className={cn("h-1.5 rounded-full bg-[rgba(255,255,255,0.08)]", width)} />
        <span className="num text-xs text-[var(--lc-text-faint)]">n/a</span>
      </div>
    );
  }

  const t = tone(pct);
  return (
    <div
      className={cn("flex items-center gap-2", className)}
      title={`Confidence ${pct}% (${t.label})`}
    >
      <div
        className={cn("h-1.5 rounded-full bg-[rgba(255,255,255,0.08)] overflow-hidden", width)}
        role="meter"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`Match confidence ${pct}%`}
      >
        <div className={cn("h-full rounded-full", t.bar)} style={{ width: `${pct}%` }} />
      </div>
      <div className="flex items-center gap-1">
        <span className={cn("num text-[11px] font-mono font-semibold", t.text)}>{pct}%</span>
        {showLabel && (
          <span className={cn("text-[10px] font-mono uppercase font-bold", t.text)}>{t.label}</span>
        )}
      </div>
    </div>
  );
});
