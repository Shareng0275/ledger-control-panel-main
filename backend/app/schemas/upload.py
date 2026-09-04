import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.enums import UploadStatus, UploadType


class UploadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    upload_id: Optional[uuid.UUID] = None
    filename: str
    upload_type: UploadType
    row_count: Optional[int] = None
    rows: Optional[int] = None
    status: UploadStatus
    validation_errors: Optional[Dict[str, Any]] = None
    created_at: datetime

    def model_post_init(self, __context: Any) -> None:
        if self.upload_id is None:
            self.upload_id = self.id
        if self.rows is None and self.row_count is not None:
            self.rows = self.row_count
        elif self.row_count is None and self.rows is not None:
            self.row_count = self.rows
