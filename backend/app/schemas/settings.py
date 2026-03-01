"""System settings schemas."""

import uuid
from typing import Any

from pydantic import BaseModel, Field


class SystemSettingsResponse(BaseModel):
    """System setting response."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    key: str
    value: Any = None
    description: str | None = None


class SystemSettingsUpdate(BaseModel):
    """Bulk update system settings request."""

    settings: dict[str, Any] = Field(..., description="Key-value pairs to update")
