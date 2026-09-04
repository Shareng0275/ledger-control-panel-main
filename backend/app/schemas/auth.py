import uuid
from datetime import datetime
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from app.models.enums import MembershipRole


class RegisterRequest(BaseModel):
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, description="Password (at least 8 characters)")
    full_name: str = Field(..., min_length=2, max_length=255, description="Full name")
    organization_name: Optional[str] = Field(
        default=None,
        min_length=2,
        max_length=255,
        description="Optional organization name to create on registration",
    )


class LoginRequest(BaseModel):
    email: EmailStr = Field(..., description="Registered email address")
    password: str = Field(..., description="Account password")


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    is_active: bool
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str = Field(..., description="Signed JWT Bearer access token")
    token: Optional[str] = Field(default=None, description="Direct token alias for frontend compatibility")
    refresh_token: str = Field(..., description="Opaque refresh token for session rotation")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Access token expiration duration in seconds")
    user: Optional[UserResponse] = Field(default=None, description="Authenticated user info")

    def model_post_init(self, __context: Any) -> None:
        if self.token is None:
            self.token = self.access_token


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., description="Active refresh token")


class MembershipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    organization_name: str
    organization_slug: str
    role: MembershipRole
    created_at: datetime


class UserMeResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    is_active: bool
    created_at: datetime
    memberships: List[MembershipResponse] = Field(default_factory=list)


class MessageResponse(BaseModel):
    message: str
