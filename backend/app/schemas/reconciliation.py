import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.enums import ReconciliationStatus


class StartReconcileRequest(BaseModel):
    statement_upload_id: Optional[uuid.UUID] = None
    ledger_upload_id: Optional[uuid.UUID] = None


class ReconcileRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    run_id: Optional[uuid.UUID] = None
    status: ReconciliationStatus
    total_transactions: int = Field(default=0)
    matched_count: int = Field(default=0)
    exception_count: int = Field(default=0)
    pending_review_count: int = Field(default=0)
    total_value_reconciled: Decimal = Field(default=Decimal("0.0000"))
    average_confidence: Optional[Decimal] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    summary: Optional[Dict[str, Any]] = None

    def model_post_init(self, __context: Any) -> None:
        if self.run_id is None:
            self.run_id = self.id
        if self.summary is None:
            self.summary = {
                "total": self.total_transactions,
                "matched": self.matched_count,
                "exceptions": self.exception_count,
                "pending_review": self.pending_review_count,
                "matched_value": float(self.total_value_reconciled),
                "exception_value": 0.0,
            }


class ConfidenceDistributionItem(BaseModel):
    """Confidence distribution for a specific transaction status category."""
    status: str
    count: int
    total_amount: Decimal = Field(default=Decimal("0.00"))
    average_confidence: Optional[Decimal] = None


class ReconciliationSummaryResponse(BaseModel):
    """Dashboard KPI summary for a reconciliation run."""
    model_config = ConfigDict(from_attributes=True)

    run_id: uuid.UUID
    status: ReconciliationStatus
    total_transactions: int
    matched_count: int
    exception_count: int
    pending_review_count: int
    total_value_reconciled: Decimal
    average_confidence: Optional[Decimal] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Confidence distribution by status category
    confidence_distribution: List[ConfidenceDistributionItem] = Field(default_factory=list)

    # Match method breakdown
    match_method_breakdown: Dict[str, int] = Field(
        default_factory=lambda: {"deterministic": 0, "fuzzy": 0, "manual": 0}
    )
