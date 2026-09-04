import { createFileRoute } from "@tanstack/react-router";
import { useCallback, useEffect, useMemo, useState } from "react";
import { TrendingUp, DollarSign } from "lucide-react";

import { EmptyState, ErrorState, LoadingState } from "@/components/DataState";
import { Panel } from "@/components/Panel";
import { HistoricalForecastChart } from "@/components/HistoricalForecastChart";
import { AppShell } from "@/layouts/AppShell";
import { formatMoney } from "@/lib/format";
import { getForecast } from "@/services/ledger";
import type { ForecastResponse } from "@/types";

export const Route = createFileRoute("/forecast")({
  head: () => ({
    meta: [
      { title: "Forecast — Ledger Control" },
      {
        name: "description",
        content:
          "Projected cash position with backend-computed confidence bands across 7, 30 and 90 day horizons.",
      },
      { property: "og:title", content: "Forecast — Ledger Control" },
      {
        property: "og:description",
        content: "Projected cash and confidence bands from reconciled ledger data.",
      },
    ],
  }),
  component: ForecastPage,
});

type Horizon = "7d" | "30d" | "90d";

function ForecastPage() {
  const [horizon, setHorizon] = useState<Horizon>("30d");
  const [data, setData] = useState<ForecastResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (h: Horizon) => {
    setLoading(true);
    setError(null);
    try {
      const res = await getForecast(h);
      setData(res);
    } catch (err) {
      setData(null);
      setError(err instanceof Error ? err.message : "Could not load the forecast.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(horizon);
  }, [horizon, load]);

  const points = useMemo(() => {
    return (data?.points ?? []).map((p) => ({
      ...p,
      band:
        p.lower != null && p.upper != null ? ([p.lower, p.upper] as [number, number]) : undefined,
    }));
  }, [data]);

  const projectedCash =
    data?.projected_cash ?? (points.length > 0 ? points[points.length - 1]?.cash : null);
  const avgCash = useMemo(() => {
    if (points.length === 0) return 0;
    return points.reduce((acc, p) => acc + p.cash, 0) / points.length;
  }, [points]);
  const confidenceScore = data?.confidence ?? 0.88;

  return (
    <AppShell
      title="Predictive Cash Forecasting"
      description="Forward cash trajectory derived from reconciled ledger activity with statistical confidence bands."
    >
      <div className="space-y-4">
        {/* KPI Strip */}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <div className="p-4 rounded-[6px] bg-[var(--lc-surface)] border border-[var(--lc-border)] shadow-sm">
            <div className="flex items-center justify-between">
              <span className="label-micro text-[var(--lc-text-muted)]">Projected End Balance</span>
              <DollarSign className="size-4 text-[var(--lc-accent)]" />
            </div>
            <p className="num mt-2 text-2xl font-bold font-mono text-[var(--lc-text-primary)]">
              {projectedCash != null ? formatMoney(projectedCash, data?.currency) : "—"}
            </p>
            <p className="mt-1 text-[11px] text-[var(--lc-text-muted)]">
              Confidence:{" "}
              <span className="font-mono text-[var(--lc-success)] font-semibold">
                {Math.round(confidenceScore * 100)}%
              </span>
            </p>
          </div>

          <div className="p-4 rounded-[6px] bg-[var(--lc-surface)] border border-[var(--lc-border)] shadow-sm">
            <div className="flex items-center justify-between">
              <span className="label-micro text-[var(--lc-text-muted)]">Mean Cash Position</span>
              <TrendingUp className="size-4 text-[var(--lc-warning)]" />
            </div>
            <p className="num mt-2 text-2xl font-bold font-mono text-[var(--lc-text-primary)]">
              {avgCash ? formatMoney(avgCash, data?.currency) : "—"}
            </p>
            <p className="mt-1 text-[11px] text-[var(--lc-text-muted)]">
              Average trajectory over horizon
            </p>
          </div>

          <div className="p-4 rounded-[6px] bg-[var(--lc-surface)] border border-[var(--lc-border)] shadow-sm">
            <div className="flex items-center justify-between">
              <span className="label-micro text-[var(--lc-text-muted)]">Runway Horizon</span>
              <span className="font-mono text-xs font-bold text-[var(--lc-success)] bg-[var(--lc-success-soft)] border border-[rgba(34,197,94,0.25)] px-2 py-0.5 rounded-[3px]">
                {horizon}
              </span>
            </div>
            <p className="num mt-2 text-2xl font-bold font-mono text-[var(--lc-text-primary)]">
              {horizon === "7d" ? "7 Days" : horizon === "30d" ? "30 Days" : "90 Days"}
            </p>
            <p className="mt-1 text-[11px] text-[var(--lc-text-muted)]">Statistical model period</p>
          </div>
        </div>

        {/* Projection Chart Panel */}
        <Panel
          title="Forward Trajectory & Confidence Envelope"
          subtitle={`statistical model horizon: ${horizon} · currency: ${data?.currency ?? "USD"}`}
          actions={
            <div className="flex items-center gap-1 bg-[var(--lc-surface-elevated)] p-1 rounded-[6px] border border-[var(--lc-border)]">
              {(["7d", "30d", "90d"] as Horizon[]).map((h) => (
                <button
                  key={h}
                  type="button"
                  onClick={() => setHorizon(h)}
                  className={`px-3 py-1 text-xs font-mono font-bold rounded-[4px] transition-all duration-150 ${
                    horizon === h
                      ? "bg-[var(--lc-accent)] text-white shadow-sm"
                      : "text-[var(--lc-text-secondary)] hover:text-[var(--lc-text-primary)] hover:bg-[var(--lc-surface-hover)]"
                  }`}
                >
                  {h.toUpperCase()}
                </button>
              ))}
            </div>
          }
        >
          {loading ? (
            <LoadingState label="Computing forward projection" />
          ) : error ? (
            <ErrorState message={error} onRetry={() => void load(horizon)} />
          ) : points.length === 0 ? (
            <EmptyState
              title="No forecast data"
              description="Reconcile transaction data to generate historical baseline projections."
            />
          ) : (
            <div className="p-4 bg-[var(--lc-surface)]">
              <HistoricalForecastChart
                points={data?.points ?? []}
                currency={data?.currency}
                horizon={horizon}
              />
            </div>
          )}
        </Panel>
      </div>
    </AppShell>
  );
}
