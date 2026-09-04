import math
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Transaction, TransactionSource
from app.schemas.forecast import (
    ForecastAnalytics,
    ForecastPoint,
    ForecastResponse,
)


class ForecastingService:
    """
    Financial Cash Forecasting and Analytics Engine.
    
    Methodology:
    1. Aggregates historical transaction cash flows per day from bank statement and ledger data.
    2. Computes baseline cumulative cash position and daily net cash drift using Exponentially
       Weighted Moving Averages (EWMA) and Ordinary Least Squares (OLS) linear trend estimation.
    3. Calculates historical daily volatility (standard deviation of daily net flows).
    4. Projects future daily cash balance for the requested horizon (7d, 30d, 90d) with expanding
       confidence uncertainty intervals (scaling with sqrt(h) according to random walk drift theory).
    5. Computes explainable analytics including burn/growth trend direction, historical daily average,
       and volatility.
    """

    HORIZON_MAP: Dict[str, int] = {
        "7d": 7,
        "30d": 30,
        "90d": 90,
    }

    @classmethod
    async def generate_forecast(
        cls,
        db: AsyncSession,
        organization_id: uuid.UUID,
        horizon_str: str,
    ) -> ForecastResponse:
        """
        Generates a statistical cash forecast and financial analytics for an organization.
        """
        horizon_days = cls.HORIZON_MAP.get(horizon_str)
        if not horizon_days:
            horizon_days = 30
            horizon_str = "30d"

        # 1. Fetch organization transactions ordered by date
        stmt = (
            select(Transaction)
            .where(Transaction.organization_id == organization_id)
            .order_by(Transaction.transaction_date.asc())
        )
        res = await db.execute(stmt)
        transactions = list(res.scalars().all())

        # If statement transactions exist, prioritize them to avoid double-counting ledger counterparts
        stmt_txs = [t for t in transactions if t.source == TransactionSource.STATEMENT]
        active_txs = stmt_txs if len(stmt_txs) >= 3 else transactions

        # 2. Handle Empty State
        if not active_txs:
            return ForecastResponse(
                horizon=horizon_str,
                currency="USD",
                projected_cash=None,
                confidence=None,
                points=[],
                analytics=None,
                methodology="Statistical Cash Flow Analysis",
                is_empty=True,
                message="No historical transaction data found for this organization. Ingest bank statements or ledger files to generate cash forecasts.",
            )

        # 3. Aggregate daily net cash flows
        daily_flows: Dict[date, Decimal] = {}
        for tx in active_txs:
            d = tx.transaction_date.date()
            daily_flows[d] = daily_flows.get(d, Decimal("0.0000")) + tx.amount

        sorted_dates = sorted(daily_flows.keys())
        start_date = sorted_dates[0]
        end_date = sorted_dates[-1]

        # Build dense daily timeline
        num_days = (end_date - start_date).days + 1
        dense_daily_flows: List[Tuple[date, Decimal]] = []
        cumulative_balance: Decimal = Decimal("0.0000")
        dense_cumulative: List[Tuple[date, Decimal]] = []

        curr_date = start_date
        while curr_date <= end_date:
            flow = daily_flows.get(curr_date, Decimal("0.0000"))
            dense_daily_flows.append((curr_date, flow))
            cumulative_balance += flow
            dense_cumulative.append((curr_date, cumulative_balance))
            curr_date += timedelta(days=1)

        total_tx_count = len(active_txs)
        total_history_days = len(dense_daily_flows)
        current_cash = cumulative_balance

        # 4. Handle Insufficient History (< 2 days of history)
        if total_history_days <= 1:
            points = cls._project_flat_baseline(
                current_cash=current_cash,
                start_date=end_date,
                horizon_days=horizon_days,
            )
            projected_ending = points[-1].projected_cash if points else current_cash
            return ForecastResponse(
                horizon=horizon_str,
                currency="USD",
                projected_cash=projected_ending,
                confidence=Decimal("0.5000"),
                points=points,
                analytics=ForecastAnalytics(
                    historical_average_daily_net=Decimal("0.0000"),
                    historical_daily_volatility=Decimal("0.0000"),
                    trend_direction="neutral",
                    current_cash_balance=current_cash.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                    projected_ending_cash=projected_ending.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                    net_projected_change=Decimal("0.00"),
                    historical_data_points=total_tx_count,
                    historical_days_analyzed=total_history_days,
                ),
                methodology="Baseline Flat Projection (Single data point available)",
                is_empty=False,
                message="Limited historical data available. Projections assume stationary cash balance.",
            )

        # 5. Statistical Estimation
        # (a) Historical Mean and Volatility
        flows_float = [float(f) for _, f in dense_daily_flows]
        mean_flow_float = sum(flows_float) / len(flows_float)
        
        # Sample variance & standard deviation
        variance = sum((x - mean_flow_float) ** 2 for x in flows_float) / max(1, len(flows_float) - 1)
        stdev_flow = math.sqrt(variance)
        # Ensure a minimal baseline volatility relative to current balance
        min_volatility = max(10.0, abs(float(current_cash)) * 0.005)
        effective_stdev = max(stdev_flow, min_volatility)

        # (b) Exponentially Weighted Moving Average (EWMA) of daily net cash flow
        alpha = 0.3
        ewma_flow = flows_float[0]
        for f in flows_float[1:]:
            ewma_flow = alpha * f + (1 - alpha) * ewma_flow

        # (c) Linear Trend (OLS slope on cumulative cash)
        # x = [0, 1, 2, ..., T-1], y = [C_0, C_1, ..., C_{T-1}]
        n = len(dense_cumulative)
        cum_floats = [float(c) for _, c in dense_cumulative]
        x_mean = (n - 1) / 2.0
        y_mean = sum(cum_floats) / n
        numerator = sum((i - x_mean) * (cum_floats[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        ols_slope = (numerator / denominator) if denominator > 0 else 0.0

        # Blended expected daily drift
        blended_daily_drift = Decimal(str(round(0.6 * ewma_flow + 0.4 * ols_slope, 4)))

        # (d) Base Model Confidence
        # Higher confidence with more history and lower relative volatility
        sample_factor = min(1.0, total_history_days / 30.0)
        cv = effective_stdev / (abs(float(current_cash)) + 1.0)
        vol_penalty = min(0.3, cv * 0.1)
        base_confidence = max(0.50, min(0.95, 0.70 + 0.25 * sample_factor - vol_penalty))

        # 6. Generate Forecast Points for Horizon
        points: List[ForecastPoint] = []
        last_date = end_date
        
        for h in range(1, horizon_days + 1):
            f_date = last_date + timedelta(days=h)
            date_str = f_date.isoformat()

            # Projected value: C_T + drift * h
            projected_val = current_cash + blended_daily_drift * Decimal(h)

            # Expanding 95% Confidence Band (1.96 * stdev * sqrt(h))
            uncertainty_margin = Decimal(str(round(1.96 * effective_stdev * math.sqrt(h), 2)))
            lower_bound = projected_val - uncertainty_margin
            upper_bound = projected_val + uncertainty_margin

            # Horizon-decayed confidence: 7d > 30d > 90d
            decay = 0.12 * (h / horizon_days)
            point_confidence = Decimal(str(round(max(0.40, base_confidence - decay), 4)))

            p_cash = projected_val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            p_lower = lower_bound.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            p_upper = upper_bound.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

            points.append(
                ForecastPoint(
                    date=date_str,
                    cash=p_cash,
                    projected=p_cash,
                    projected_cash=p_cash,
                    lower=p_lower,
                    lower_bound=p_lower,
                    upper=p_upper,
                    upper_bound=p_upper,
                    confidence=point_confidence,
                )
            )

        # 7. Compute Analytics
        avg_daily_net = Decimal(str(round(mean_flow_float, 2)))
        volatility_dec = Decimal(str(round(effective_stdev, 2)))
        projected_ending = points[-1].projected_cash if points else current_cash
        net_change = projected_ending - current_cash

        if blended_daily_drift > Decimal("5.00"):
            trend_dir = "positive"
        elif blended_daily_drift < Decimal("-5.00"):
            trend_dir = "negative"
        else:
            trend_dir = "neutral"

        overall_conf = Decimal(str(round(base_confidence, 4)))

        analytics = ForecastAnalytics(
            historical_average_daily_net=avg_daily_net,
            historical_daily_volatility=volatility_dec,
            trend_direction=trend_dir,
            current_cash_balance=current_cash.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            projected_ending_cash=projected_ending.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            net_projected_change=net_change.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            historical_data_points=total_tx_count,
            historical_days_analyzed=total_history_days,
        )

        return ForecastResponse(
            horizon=horizon_str,
            currency="USD",
            projected_cash=projected_ending.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            confidence=overall_conf,
            points=points,
            analytics=analytics,
            methodology="EWMA & OLS Linear Drift with Random-Walk Expanding Volatility Confidence Bands",
            is_empty=False,
        )

    @classmethod
    def _project_flat_baseline(
        cls,
        current_cash: Decimal,
        start_date: date,
        horizon_days: int,
    ) -> List[ForecastPoint]:
        """Project flat baseline with standard 5% expanding uncertainty band for single-point datasets."""
        points: List[ForecastPoint] = []
        base_val = current_cash.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        baseline_margin = max(Decimal("100.00"), abs(base_val) * Decimal("0.05"))

        for h in range(1, horizon_days + 1):
            f_date = start_date + timedelta(days=h)
            date_str = f_date.isoformat()
            margin = (baseline_margin * Decimal(str(round(math.sqrt(h), 2)))).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            p_lower = base_val - margin
            p_upper = base_val + margin
            conf = Decimal(str(round(max(0.40, 0.60 - 0.15 * (h / horizon_days)), 4)))

            points.append(
                ForecastPoint(
                    date=date_str,
                    cash=base_val,
                    projected=base_val,
                    projected_cash=base_val,
                    lower=p_lower,
                    lower_bound=p_lower,
                    upper=p_upper,
                    upper_bound=p_upper,
                    confidence=conf,
                )
            )
        return points
