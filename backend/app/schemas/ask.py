from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class AskRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    question: str = Field(
        ...,
        min_length=3,
        max_length=1000,
        description="Natural language question regarding financial reconciliation, exceptions, transactions, or cash forecast",
    )


class SupportingRowDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique record identifier")
    type: str = Field(..., description="Entity type ('transaction', 'exception', 'reconciliation_run', 'forecast')")
    date: Optional[str] = Field(default=None, description="Transaction or event date")
    description: Optional[str] = Field(default=None, description="Description or event summary")
    amount: Optional[str] = Field(default=None, description="Monetary value formatted as string")
    status: Optional[str] = Field(default=None, description="Status (e.g. matched, exception, pending_review)")
    reason: Optional[str] = Field(default=None, description="Exception reason or explanation")
    confidence: Optional[str] = Field(default=None, description="Confidence score")


class AskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    answer: str = Field(..., description="Synthesized financial AI response")
    supporting_rows: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Real underlying database records validating the answer",
    )
