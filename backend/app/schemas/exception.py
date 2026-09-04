import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.enums import ExceptionPriority, ExceptionStatus, TransactionSource, TransactionStatus
from app.schemas.common import PaginatedResponse


class TransactionSummaryDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source: TransactionSource
    transaction_date: datetime
    description: str
    normalized_description: Optional[str] = None
    amount: Decimal
    currency: str
    external_reference: Optional[str] = None
    normalized_reference: Optional[str] = None
    status: TransactionStatus
    confidence: Optional[Decimal] = None


class ExceptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    reconciliation_run_id: uuid.UUID
    transaction_id: uuid.UUID
    best_candidate_transaction_id: Optional[uuid.UUID] = None
    reason: str = Field(..., alias="reason_text")
    priority: ExceptionPriority
    status: ExceptionStatus
    resolution_action: Optional[str] = None
    resolved_by: Optional[uuid.UUID] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime

    # Rich Transaction Data
    amount: Optional[Decimal] = None
    date: Optional[datetime] = None
    description: Optional[str] = None
    currency: Optional[str] = None
    confidence: Optional[Decimal] = None
    transaction: Optional[TransactionSummaryDTO] = None
    best_candidate_transaction: Optional[TransactionSummaryDTO] = None
    best_candidate: Optional[Dict[str, Any]] = None
    statement_side: Optional[Dict[str, Any]] = None
    ledger_side: Optional[Dict[str, Any]] = None

    def model_post_init(self, __context: Any) -> None:
        if self.transaction:
            if self.amount is None:
                self.amount = self.transaction.amount
            if self.date is None:
                self.date = self.transaction.transaction_date
            if self.description is None:
                self.description = self.transaction.description
            if self.currency is None:
                self.currency = self.transaction.currency
            if self.confidence is None:
                self.confidence = self.transaction.confidence
            if self.statement_side is None:
                self.statement_side = {
                    "id": str(self.transaction.id),
                    "date": self.transaction.transaction_date.isoformat(),
                    "description": self.transaction.description,
                    "amount": float(self.transaction.amount),
                    "source": self.transaction.source.value if hasattr(self.transaction.source, "value") else str(self.transaction.source),
                    "confidence": float(self.transaction.confidence) if self.transaction.confidence else None,
                }
        if self.best_candidate_transaction and self.best_candidate is None:
            cand = {
                "id": str(self.best_candidate_transaction.id),
                "date": self.best_candidate_transaction.transaction_date.isoformat(),
                "description": self.best_candidate_transaction.description,
                "amount": float(self.best_candidate_transaction.amount),
                "source": self.best_candidate_transaction.source.value if hasattr(self.best_candidate_transaction.source, "value") else str(self.best_candidate_transaction.source),
                "confidence": float(self.best_candidate_transaction.confidence) if self.best_candidate_transaction.confidence else None,
            }
            self.best_candidate = cand
            if self.ledger_side is None:
                self.ledger_side = cand


class ExceptionReviewDetailResponse(BaseModel):
    """Full detail schema tailored for frontend review drawer."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    reconciliation_run_id: uuid.UUID
    priority: ExceptionPriority
    status: ExceptionStatus
    reason: str
    created_at: datetime
    resolved_at: Optional[datetime] = None
    resolution_action: Optional[str] = None

    # Statement side
    statement_transaction: TransactionSummaryDTO

    # Ledger candidate side (if available)
    candidate_transaction: Optional[TransactionSummaryDTO] = None

    # Score breakdown & AI/fuzzy explanation
    explanation_details: Dict[str, Any] = Field(default_factory=dict)


class ResolveExceptionRequest(BaseModel):
    action: str = Field(..., description="'confirm_match' or 'reject'")
    candidate_id: Optional[uuid.UUID] = Field(default=None, description="Optional override candidate transaction ID")
    note: Optional[str] = Field(default=None, description="Optional analyst resolution note")


class ResolveExceptionResponse(BaseModel):
    exception_id: uuid.UUID
    status: str
    message: str
    match_id: Optional[uuid.UUID] = None


class BulkResolveRequest(BaseModel):
    exception_ids: List[uuid.UUID] = Field(..., min_length=1, description="List of exception IDs to resolve")
    action: str = Field(..., description="'confirm_match' or 'reject'")
    note: Optional[str] = Field(default=None, description="Optional resolution note applied to all")


class BulkResolveResponse(BaseModel):
    total_requested: int
    resolved_count: int
    failed_count: int
    results: List[ResolveExceptionResponse] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


class ExceptionListResponse(PaginatedResponse[ExceptionResponse]):
    exceptions: List[ExceptionResponse] = Field(default_factory=list)

    def model_post_init(self, __context: Any) -> None:
        if not self.exceptions and self.items:
            self.exceptions = self.items
