from datetime import datetime
from typing import Dict, Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(default="healthy", description="Application health status")
    app_name: str = Field(..., description="Application name")
    environment: str = Field(..., description="Current environment")
    timestamp: datetime = Field(..., description="Current server UTC timestamp")
    database_connected: bool = Field(..., description="Database connectivity status")
    details: Optional[Dict[str, str]] = Field(default=None, description="Detailed subsystem status")
