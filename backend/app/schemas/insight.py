import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class RunInsight(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, description="Unique insight identifier")
    organization_id: Optional[uuid.UUID] = Field(default=None, description="Tenant organization ID")
    related_transaction_id: Optional[uuid.UUID] = Field(default=None, description="Associated transaction ID")
    transaction_id: Optional[uuid.UUID] = Field(default=None, description="Compatibility alias for transaction ID")
    exception_id: Optional[uuid.UUID] = Field(default=None, description="Associated exception ID")
    reconciliation_run_id: Optional[uuid.UUID] = Field(default=None, description="Associated reconciliation run ID")

    category: str = Field(
        ...,
        description="Anomaly category: 'unusual_amount', 'unusual_frequency', 'near_duplicate', 'suspicious_mismatch', 'high_risk_exception'",
    )
    type: str = Field(..., description="Compatibility alias for category")
    title: str = Field(..., description="Human-readable insight headline")
    severity: str = Field(..., description="Severity level: 'low', 'medium', 'high', 'critical'")
    explanation: str = Field(..., description="Evidence-based calculation and explanation")
    message: str = Field(..., description="Compatibility alias for explanation")

    score: Optional[float] = Field(default=None, description="Anomaly confidence / deviation score (0.0 to 1.0)")
    score_details: Optional[Dict[str, Any]] = Field(default=None, description="Statistical breakdown metadata")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of insight detection")

    def model_post_init(self, __context: Any) -> None:
        if self.transaction_id is None and self.related_transaction_id is not None:
            self.transaction_id = self.related_transaction_id
        elif self.related_transaction_id is None and self.transaction_id is not None:
            self.related_transaction_id = self.transaction_id

        if not self.type and self.category:
            self.type = self.category
        if not self.message and self.explanation:
            self.message = self.explanation


class InsightsListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    insights: List[RunInsight] = Field(default_factory=list, description="List of detected financial insights")
    total: int = Field(default=0, description="Total number of insights matching filters")
    severity_counts: Dict[str, int] = Field(
        default_factory=lambda: {"critical": 0, "high": 0, "medium": 0, "low": 0},
        description="Counts of insights grouped by severity",
    )
    category_counts: Dict[str, int] = Field(
        default_factory=dict,
        description="Counts of insights grouped by category",
    )
