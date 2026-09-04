import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.common import PaginatedResponse


class AuditEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    timestamp: datetime = Field(..., alias="created_at", description="UTC timestamp of the action")
    actor: Optional[str] = Field(default="System", description="Full name or identifier of acting user")
    actor_id: Optional[uuid.UUID] = Field(default=None, description="User ID of actor")
    action: str = Field(..., description="Action performed (e.g. auth.login, upload.created, reconciliation.completed)")
    entity_type: str = Field(..., description="Entity classification (e.g. User, Upload, ReconciliationRun, Exception)")
    entity_id: Optional[uuid.UUID] = Field(default=None, description="Primary key of modified/affected entity")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Contextual action metadata")
    ip_address: Optional[str] = Field(default=None, description="IP address of requester")


class AuditListResponse(PaginatedResponse[AuditEntry]):
    entries: List[AuditEntry] = Field(
        default_factory=list,
        description="Audit entries list for Lovable frontend compatibility",
    )

    def model_post_init(self, __context: Any) -> None:
        if not self.entries and self.items:
            self.entries = self.items
