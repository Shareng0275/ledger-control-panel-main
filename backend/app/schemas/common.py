from typing import Any, Generic, List, Optional, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorResponse(BaseModel):
    error: str = Field(..., description="High-level error classification")
    detail: Any = Field(..., description="Human-readable explanation or structured validation details")
    status_code: int = Field(..., description="HTTP status code")
    code: Optional[str] = Field(default=None, description="Optional application-level error code")


class SuccessResponse(BaseModel):
    message: str = Field(..., description="Success message")
    data: Optional[Any] = Field(default=None, description="Optional payload")


class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T] = Field(default_factory=list, description="Page items")
    total: int = Field(..., description="Total count across all pages")
    page: int = Field(..., description="Current page number (1-indexed)")
    page_size: int = Field(..., description="Number of items per page")
    total_pages: int = Field(..., description="Total number of available pages")
    has_next: bool = Field(..., description="Whether a next page exists")
    has_prev: bool = Field(..., description="Whether a previous page exists")
