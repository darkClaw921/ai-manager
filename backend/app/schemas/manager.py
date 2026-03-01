"""Manager schemas: list with stats, detailed statistics."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ManagerWithStats(BaseModel):
    """Manager info with aggregate counts."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    email: str
    full_name: str
    is_active: bool
    created_at: datetime
    channels_count: int = Field(default=0, description="Number of channels owned")
    leads_count: int = Field(default=0, description="Number of leads across channels")
    conversations_count: int = Field(default=0, description="Number of conversations across channels")


class ManagerDetailStats(BaseModel):
    """Detailed manager statistics."""

    manager: ManagerWithStats
    leads_by_status: dict[str, int] = Field(default_factory=dict, description="Lead counts grouped by status")
    conversations_by_status: dict[str, int] = Field(default_factory=dict, description="Conversation counts grouped by status")
    recent_activity: list[dict[str, Any]] = Field(default_factory=list, description="Recent activity entries")
