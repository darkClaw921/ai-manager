"""Admin user schemas: create, update, response."""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models.user import UserRole


class UserResponse(BaseModel):
    """Admin user response (no password_hash)."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime | None = None


class UserCreate(BaseModel):
    """Create admin user request."""

    email: EmailStr = Field(..., description="User email")
    password: str = Field(..., min_length=6, description="User password")
    full_name: str = Field(..., min_length=1, max_length=255, description="Full name")
    role: UserRole = Field(default=UserRole.MANAGER, description="User role")
    is_active: bool = Field(default=True, description="Is user active")


class UserUpdate(BaseModel):
    """Update admin user request. All fields optional."""

    email: EmailStr | None = None
    password: str | None = Field(None, min_length=6, description="New password")
    full_name: str | None = Field(None, min_length=1, max_length=255)
    role: UserRole | None = None
    is_active: bool | None = None
