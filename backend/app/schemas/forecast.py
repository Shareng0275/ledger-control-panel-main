from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ForecastPoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date: str = Field(..., description="Projected calendar date (YYYY-MM-DD)")
    projected_cash: Decimal = Field(..., description="Expected cash balance on date")
    lower_bound: Decimal = Field(..., description="95% confidence lower uncertainty bound")
    upper_bound: Decimal = Field(..., description="95% confidence upper uncertainty bound")
    confidence: Decimal = Field(..., description="Forecast confidence factor (0.0 to 1.0)")

    # Aliases for frontend flexibility
    cash: Optional[Decimal] = Field(default=None, description="Compatibility alias for projected_cash")
    projected: Optional[Decimal] = Field(default=None, description="Compatibility alias for projected_cash")
    lower: Optional[Decimal] = Field(default=None, description="Compatibility alias for lower_bound")
    upper: Optional[Decimal] = Field(default=None, description="Compatibility alias for upper_bound")


class ForecastAnalytics(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    historical_average_daily_net: Decimal = Field(..., description="Average historical daily net cash flow")
    historical_daily_volatility: Decimal = Field(..., description="Standard deviation of daily net cash flows")
    trend_direction: str = Field(..., description="Current trajectory: 'positive', 'negative', or 'neutral'")
    current_cash_balance: Decimal = Field(..., description="Current starting cash position")
    projected_ending_cash: Decimal = Field(..., description="Projected cash balance at end of horizon")
    net_projected_change: Decimal = Field(..., description="Net expected cash change over horizon")
    historical_data_points: int = Field(..., description="Number of historical transactions evaluated")
    historical_days_analyzed: int = Field(..., description="Number of distinct calendar days in historical window")


class ForecastResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    horizon: str = Field(..., description="'7d', '30d', '90d'")
    currency: str = Field(default="USD", description="Currency denomination")
    projected_cash: Optional[Decimal] = Field(default=None, description="Ending projected cash balance")
    confidence: Optional[Decimal] = Field(default=None, description="Overall forecast confidence score (0.0 to 1.0)")
    points: List[ForecastPoint] = Field(default_factory=list, description="Daily projected forecast points with confidence bands")
    analytics: Optional[ForecastAnalytics] = Field(default=None, description="Financial analytics metrics")
    methodology: str = Field(default="Statistical Cash Flow Analysis", description="Statistical forecasting model used")
    is_empty: bool = Field(default=False, description="True if no historical transaction data exists")
    message: Optional[str] = Field(default=None, description="Explanatory notes regarding dataset or projection")
