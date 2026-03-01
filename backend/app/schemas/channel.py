"""Channel schemas: create, update, response."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.channel import ChannelType


class ChannelCreate(BaseModel):
    """Create channel request."""

    type: ChannelType = Field(..., description="Channel type")
    name: str = Field(..., min_length=1, max_length=255, description="Channel name")
    config: dict[str, Any] | None = Field(default_factory=dict, description="Channel-specific config")
    is_active: bool = True
    qualification_script_id: uuid.UUID | None = None


class ChannelUpdate(BaseModel):
    """Update channel request. All fields optional."""

    name: str | None = Field(None, min_length=1, max_length=255)
    config: dict[str, Any] | None = None
    is_active: bool | None = None
    qualification_script_id: uuid.UUID | None = None


class ChannelResponse(BaseModel):
    """Channel response."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    type: ChannelType
    name: str
    config: dict[str, Any] | None = None
    is_active: bool
    qualification_script_id: uuid.UUID | None = None
    qualification_script_name: str | None = None
    created_at: datetime
    updated_at: datetime | None = None
