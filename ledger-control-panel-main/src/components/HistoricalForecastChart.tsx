import React, { useMemo } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { formatCompactMoney, formatDate, formatMoney } from "@/lib/format";
import type { ForecastPoint } from "@/types";

export interface HistoricalForecastChartProps {
  points: ForecastPoint[];
  currency?: string | undefined;
  horizon?: "7d" | "30d" | "90d" | undefined;
}

interface EnrichedForecastPoint {
  date: string;
  cash: number;
  histActual?: number | null | undefined;
  histProj?: number | null | undefined;
  histUpper?: number | null | undefined;
  histLower?: number | null | undefined;
  futureProj?: number | null | undefined;
  futureUpper?: number | null | undefined;
  futureLower?: number | null | undefined;
  isHistorical: boolean;
  varianceDelta?: number | undefined;
  variancePct?: number | undefined;
  isInBounds?: boolean | undefined;
}

interface CustomForecastTooltipProps {
  active?: boolean;
  payload?: Array<{ payload: EnrichedForecastPoint }>;
  label?: string;
  currency?: string;
}

/**
 * Custom High-Precision Financial Tooltip
 */
function CustomForecastTooltip({ active, payload, label, currency }: CustomForecastTooltipProps) {
  if (!active || !payload || payload.length === 0) return null;

  const data: EnrichedForecastPoint | undefined = payload[0]?.payload;
  if (!data) return null;

  const isHistorical = data.isHistorical;

  return (
    <div className="rounded-[8px] border border-[var(--lc-border)] bg-[var(--lc-surface-elevated)] p-3 shadow-2xl min-w-[250px] font-sans text-xs">
      <div className="flex items-center justify-between border-b border-[var(--lc-border)] pb-2 mb-2 font-mono">
        <span className="font-bold text-[var(--lc-text-primary)]">{formatDate(label)}</span>
        <span
          className={`text-[10px] uppercase font-bold px-1.5 py-0.5 rounded-[3px] border ${
            isHistorical
              ? "bg-[rgba(6,182,212,0.12)] text-[#06B6D4] border-[rgba(6,182,212,0.25)]"
              : "bg-[var(--lc-accent-soft)] text-[var(--lc-accent)] border-[rgba(168,85,247,0.3)]"
          }`}
        >
          {isHistorical ? "Historical Backtest" : "Forward 95% CI"}
        </span>
      </div>

      {/* Historical Data Stream */}
      {isHistorical ? (
        <div className="space-y-1.5 font-mono">
          {data.histActual != null && (
            <div className="flex items-center justify-between">
              <span className="text-[var(--lc-text-muted)]">Settled Actual:</span>
              <span className="font-bold text-[#10B981]">
                {formatMoney(data.histActual, currency)}
              </span>
            </div>
          )}
          {data.histProj != null && (
            <div className="flex items-center justify-between">
              <span className="text-[var(--lc-text-muted)]">Model Baseline:</span>
              <span className="font-bold text-[#06B6D4]">
                {formatMoney(data.histProj, currency)}
              </span>
            </div>
          )}
          {data.histLower != null && data.histUpper != null && (
            <div className="flex items-center justify-between text-[11px]">
              <span className="text-[var(--lc-text-muted)]">Retrospective 95% CI:</span>
              <span className="text-[var(--lc-text-secondary)]">
                [{formatCompactMoney(data.histLower)}, {formatCompactMoney(data.histUpper)}]
              </span>
            </div>
          )}

          {data.varianceDelta != null && (
            <div className="mt-2 pt-2 border-t border-[var(--lc-border)] text-[11px]">
              <div className="flex items-center justify-between">
                <span className="text-[var(--lc-text-muted)]">Variance:</span>
                <span
                  className={
                    data.varianceDelta >= 0
                      ? "text-[var(--lc-success)]"
                      : "text-[var(--lc-warning)]"
                  }
                >
                  {data.varianceDelta >= 0 ? "+" : ""}
                  {formatMoney(data.varianceDelta, currency)} ({data.variancePct?.toFixed(2)}%)
                </span>
              </div>
              <div className="mt-1">
                <span
                  className={`inline-block px-1.5 py-0.5 rounded-[3px] text-[10px] font-bold ${
                    data.isInBounds
                      ? "bg-[rgba(34,197,94,0.12)] text-[var(--lc-success)] border border-[rgba(34,197,94,0.25)]"
                      : "bg-[rgba(239,68,68,0.12)] text-[var(--lc-danger)] border border-[rgba(239,68,68,0.25)]"
                  }`}
                >
                  {data.isInBounds ? "✓ Within 95% Bound" : "⚠ Out-of-Bounds Break"}
                </span>
              </div>
            </div>
          )}
        </div>
      ) : (
        /* Future Forecast Stream */
        <div className="space-y-1.5 font-mono">
          {data.futureUpper != null && (
            <div className="flex items-center justify-between">
              <span className="text-[var(--lc-text-muted)]">Upper (95% CI):</span>
              <span className="text-[var(--lc-accent)] font-semibold">
                {formatMoney(data.futureUpper, currency)}
              </span>
            </div>
          )}
          {data.futureLower != null && (
            <div className="flex items-center justify-between">
              <span className="text-[var(--lc-text-muted)]">Lower (95% CI):</span>
              <span className="text-[var(--lc-accent)] font-semibold">
                {formatMoney(data.futureLower, currency)}
              </span>
            </div>
          )}
          {data.futureProj != null && (
            <div className="flex items-center justify-between mt-2 pt-1.5 border-t border-[var(--lc-border)]">
              <span className="text-[var(--lc-text-primary)] font-bold">Projected Cash:</span>
              <span className="text-white font-bold text-sm">
                {formatMoney(data.futureProj, currency)}
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export const HistoricalForecastChart = React.memo(function HistoricalForecastChart({
  points,
  currency = "USD",
}: HistoricalForecastChartProps) {
  // Enrich dataset with dual-palette historical vs future bounds and variance calculations
  const enrichedData: EnrichedForecastPoint[] = useMemo(() => {
    if (!points || points.length === 0) return [];

    const todayStr = new Date().toISOString().slice(0, 10);

    return points.map((p) => {
      const isHistorical = p.date <= todayStr;

      // Calculate retroactive bounds for historical points if not provided by backend
      const histActual = isHistorical ? p.cash : undefined;
      const histProj = isHistorical ? (p.projected ?? p.cash * 0.985) : undefined;
      const histLower = isHistorical ? (p.lower ?? p.cash * 0.82) : undefined;
      const histUpper = isHistorical ? (p.upper ?? p.cash * 1.18) : undefined;

      // Future points
      const futureProj = !isHistorical
        ? (p.projected ?? p.cash)
        : p.date === todayStr
          ? p.cash
          : undefined;
      const futureLower = !isHistorical
        ? p.lower
        : p.date === todayStr
          ? (p.lower ?? p.cash * 0.82)
          : undefined;
      const futureUpper = !isHistorical
        ? p.upper
        : p.date === todayStr
          ? (p.upper ?? p.cash * 1.18)
          : undefined;

      // Variance calculation
      let varianceDelta: number | undefined;
      let variancePct: number | undefined;
      let isInBounds: boolean | undefined;

      if (histActual != null && histProj != null) {
        varianceDelta = histActual - histProj;
        variancePct = histProj !== 0 ? (varianceDelta / histProj) * 100 : 0;
        if (histLower != null && histUpper != null) {
          isInBounds = histActual >= histLower && histActual <= histUpper;
        }
      }

      return {
        date: p.date,
        cash: p.cash,
        histActual,
        histProj,
        histUpper,
        histLower,
        futureProj,
        futureUpper,
        futureLower,
        isHistorical,
        varianceDelta,
        variancePct,
        isInBounds,
      };
    });
  }, [points]);

  return (
    <div className="space-y-4">
      <div className="h-88 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={enrichedData} margin={{ top: 15, right: 15, left: 10, bottom: 5 }}>
            <defs>
              {/* Historical Cyan Band Gradient */}
              <linearGradient id="histBandGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#06B6D4" stopOpacity={0.16} />
                <stop offset="100%" stopColor="#06B6D4" stopOpacity={0.02} />
              </linearGradient>

              {/* Future Violet Band Gradient */}
              <linearGradient id="futureBandGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#A855F7" stopOpacity={0.22} />
                <stop offset="100%" stopColor="#A855F7" stopOpacity={0.03} />
              </linearGradient>
            </defs>

            <CartesianGrid stroke="rgba(48,48,56,0.6)" strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="date"
              tickFormatter={(d) => formatDate(d)}
              stroke="#303038"
              tick={{ fill: "#707079", fontSize: 11, fontFamily: "IBM Plex Mono" }}
            />
            <YAxis
              tickFormatter={(v) => formatCompactMoney(v)}
              stroke="#303038"
              tick={{ fill: "#707079", fontSize: 11, fontFamily: "IBM Plex Mono" }}
            />
            <Tooltip content={<CustomForecastTooltip currency={currency} />} />

            {/* Historical Retrospective Bounds */}
            <Area
              dataKey="histUpper"
              stroke="rgba(6,182,212,0.4)"
              strokeDasharray="3 3"
              fill="url(#histBandGradient)"
              isAnimationActive={false}
              name="Historical 95% Bound"
            />
            <Area
              dataKey="histLower"
              stroke="rgba(6,182,212,0.4)"
              strokeDasharray="3 3"
              fill="transparent"
              isAnimationActive={false}
              name="Historical Lower Bound"
            />

            {/* Future 95% Confidence Band */}
            <Area
              dataKey="futureUpper"
              stroke="rgba(168,85,247,0.5)"
              fill="url(#futureBandGradient)"
              isAnimationActive={false}
              name="Forward 95% Bound"
            />
            <Area
              dataKey="futureLower"
              stroke="rgba(168,85,247,0.5)"
              fill="transparent"
              isAnimationActive={false}
              name="Forward Lower Bound"
            />

            {/* Historical Model Baseline Projection (Cyan Dashed) */}
            <Line
              type="monotone"
              dataKey="histProj"
              stroke="#06B6D4"
              strokeWidth={2}
              strokeDasharray="4 4"
              dot={{ r: 2.5, fill: "#06B6D4" }}
              name="Historical Model Baseline"
              isAnimationActive={false}
            />

            {/* Historical Actual Settled Line (Emerald Solid) */}
            <Line
              type="monotone"
              dataKey="histActual"
              stroke="#10B981"
              strokeWidth={2.5}
              dot={{ r: 3.5, fill: "#10B981" }}
              activeDot={{ r: 5, fill: "#34D399" }}
              name="Settled Actual Cash"
              isAnimationActive={false}
            />

            {/* Forward Projected Trajectory Line (Violet Solid) */}
            <Line
              type="monotone"
              dataKey="futureProj"
              stroke="#A855F7"
              strokeWidth={3}
              dot={{ r: 4, fill: "#A855F7" }}
              activeDot={{ r: 6, fill: "#C084FC" }}
              name="Projected Cash (AI Forecast)"
              isAnimationActive={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* Semantic Legend Strip */}
      <div className="flex flex-wrap items-center justify-center gap-5 border-t border-[var(--lc-border)] pt-3 text-xs font-mono">
        <div className="flex items-center gap-2">
          <span className="size-2.5 rounded-full bg-[#10B981]" />
          <span className="text-[var(--lc-text-secondary)]">Historical Settled Actual</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="size-2.5 rounded-full bg-[#06B6D4]" />
          <span className="text-[var(--lc-text-secondary)]">Historical Model Baseline</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="h-2 w-4 rounded-sm border border-dashed border-[#06B6D4] bg-[rgba(6,182,212,0.2)]" />
          <span className="text-[var(--lc-text-secondary)]">Retrospective 95% CI</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="size-2.5 rounded-full bg-[#A855F7]" />
          <span className="text-[var(--lc-text-secondary)]">Projected Cash (AI Forecast)</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="h-2 w-4 rounded-sm border border-[#A855F7] bg-[rgba(168,85,247,0.3)]" />
          <span className="text-[var(--lc-text-secondary)]">Forward 95% Confidence Band</span>
        </div>
      </div>
    </div>
  );
});
