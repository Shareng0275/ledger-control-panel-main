import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.enums import MatchMethod, TransactionSource, TransactionStatus
from app.schemas.common import PaginatedResponse


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    date: datetime = Field(..., alias="transaction_date", description="Transaction date")
    description: str
    normalized_description: Optional[str] = None
    amount: Decimal = Field(..., description="Exact monetary amount")
    currency: str = "USD"
    source: TransactionSource
    status: TransactionStatus
    confidence: Optional[Decimal] = None
    external_ref: Optional[str] = Field(default=None, alias="external_reference")
    created_at: datetime


class MatchInfoDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    method: MatchMethod
    confidence: Decimal
    score_details: Optional[Dict[str, Any]] = None
    counterpart_transaction_id: Optional[uuid.UUID] = None
    counterpart_description: Optional[str] = None
    counterpart_amount: Optional[Decimal] = None
    counterpart_date: Optional[datetime] = None


class AuditEntryDTO(BaseModel):
    id: uuid.UUID
    action: str
    actor_id: uuid.UUID
    details: Optional[Dict[str, Any]] = None
    created_at: datetime


class TransactionDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    date: datetime = Field(..., alias="transaction_date")
    description: str
    normalized_description: Optional[str] = None
    amount: Decimal
    currency: str
    source: TransactionSource
    external_reference: Optional[str] = None
    normalized_reference: Optional[str] = None
    status: TransactionStatus
    confidence: Optional[Decimal] = None
    reconciliation_run_id: Optional[uuid.UUID] = None
    created_at: datetime

    # Match information (if matched)
    match_info: Optional[MatchInfoDTO] = None

    # Relevant audit history
    audit_history: List[AuditEntryDTO] = Field(default_factory=list)


class TransactionListResponse(PaginatedResponse[TransactionResponse]):
    # Provide transactions alias for direct frontend list consumption
    transactions: List[TransactionResponse] = Field(
        default_factory=list,
        description="Transactions list for Lovable frontend compatibility",
    )

    def model_post_init(self, __context: Any) -> None:
        if not self.transactions and self.items:
            self.transactions = self.items
