import React from "react";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";
import type { ReconcileSummary } from "@/types";
import { formatMoney } from "@/lib/format";

const STATUS_COLORS = {
  matched: "#22C55E",
  pending: "#F59E0B",
  exceptions: "#EF4444",
};

interface SummaryChartProps {
  summary: ReconcileSummary;
}

export const ReconciliationSummaryChart = React.memo(function ReconciliationSummaryChart({
  summary,
}: SummaryChartProps) {
  const matched = summary.matched ?? 0;
  const pending = summary.pending_review ?? 0;
  const exceptions = summary.exceptions ?? 0;
  const total = summary.total || matched + pending + exceptions || 1;

  const data = [
    { name: "Matched", value: matched, color: STATUS_COLORS.matched },
    { name: "Pending Review", value: pending, color: STATUS_COLORS.pending },
    { name: "Exceptions", value: exceptions, color: STATUS_COLORS.exceptions },
  ].filter((d) => d.value > 0);

  const matchRate = Math.round((matched / total) * 100);

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 items-center bg-[var(--lc-surface)] p-4 rounded-[6px] border border-[var(--lc-border)] shadow-sm">
      <div className="relative h-48 w-full flex items-center justify-center">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={
                data.length > 0
                  ? data
                  : [{ name: "No Data", value: 1, color: "rgba(255,255,255,0.1)" }]
              }
              cx="50%"
              cy="50%"
              innerRadius={52}
              outerRadius={78}
              paddingAngle={data.length > 1 ? 4 : 0}
              dataKey="value"
              stroke="none"
              isAnimationActive={false}
            >
              {(data.length > 0 ? data : [{ color: "rgba(255,255,255,0.1)" }]).map(
                (entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ),
              )}
            </Pie>
            <Tooltip
              formatter={(value, name) => [`${value} records`, `${name}`]}
              contentStyle={{
                backgroundColor: "#1E1E23",
                border: "1px solid #303038",
                borderRadius: "6px",
                fontSize: "12px",
                color: "#F5F5F7",
                boxShadow: "0 4px 12px rgba(0,0,0,0.5)",
              }}
              itemStyle={{ color: "#F5F5F7" }}
            />
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center text-center">
          <span className="text-2xl font-bold font-mono text-[var(--lc-text-primary)]">
            {matchRate}%
          </span>
          <span className="text-[10px] uppercase font-semibold text-[var(--lc-text-muted)] tracking-wider">
            Matched
          </span>
        </div>
      </div>

      <div className="space-y-2.5">
        <div className="flex items-center justify-between p-2.5 rounded-[6px] bg-[rgba(34,197,94,0.06)] border border-[rgba(34,197,94,0.2)]">
          <div className="flex items-center gap-2">
            <span
              className="size-2 rounded-full bg-[var(--lc-success)] shadow-[0_0_6px_var(--lc-success)]"
              aria-hidden
            />
            <span className="text-xs font-medium text-[var(--lc-text-primary)]">
              Deterministic & AI Matched
            </span>
          </div>
          <div className="text-right">
            <span className="text-xs font-mono font-bold text-[var(--lc-success)]">{matched}</span>
            {summary.matched_value != null ? (
              <span className="block text-[10px] font-mono text-[var(--lc-text-muted)]">
                {formatMoney(summary.matched_value)}
              </span>
            ) : null}
          </div>
        </div>

        <div className="flex items-center justify-between p-2.5 rounded-[6px] bg-[rgba(245,158,11,0.06)] border border-[rgba(245,158,11,0.2)]">
          <div className="flex items-center gap-2">
            <span
              className="size-2 rounded-full bg-[var(--lc-warning)] shadow-[0_0_6px_var(--lc-warning)]"
              aria-hidden
            />
            <span className="text-xs font-medium text-[var(--lc-text-primary)]">
              Pending Review
            </span>
          </div>
          <div className="text-right">
            <span className="text-xs font-mono font-bold text-[var(--lc-warning)]">{pending}</span>
          </div>
        </div>

        <div className="flex items-center justify-between p-2.5 rounded-[6px] bg-[rgba(239,68,68,0.06)] border border-[rgba(239,68,68,0.2)]">
          <div className="flex items-center gap-2">
            <span
              className="size-2 rounded-full bg-[var(--lc-danger)] shadow-[0_0_6px_var(--lc-danger)]"
              aria-hidden
            />
            <span className="text-xs font-medium text-[var(--lc-text-primary)]">
              Exceptions & Breaks
            </span>
          </div>
          <div className="text-right">
            <span className="text-xs font-mono font-bold text-[var(--lc-danger)]">
              {exceptions}
            </span>
            {summary.exception_value != null ? (
              <span className="block text-[10px] font-mono text-[var(--lc-text-muted)]">
                {formatMoney(summary.exception_value)}
              </span>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
});
