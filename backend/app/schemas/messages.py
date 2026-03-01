"""Pydantic schemas for channel messages (request/response)."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class IncomingMessageSchema(BaseModel):
    """Schema for incoming messages from any channel."""

    external_id: str = Field(..., description="User identifier in the channel")
    text: str = Field(..., min_length=1, description="Message text content")
    channel_type: str = Field(..., description="Channel type: telegram | web_widget")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Channel-specific data")
    timestamp: datetime | None = Field(default=None, description="Message timestamp (auto-set if None)")


class OutgoingMessageSchema(BaseModel):
    """Schema for outgoing messages to any channel."""

    text: str = Field(..., description="Response text to send")
    message_type: str = Field(default="text", description="Message type: text | booking | typing")
    data: dict[str, Any] = Field(default_factory=dict, description="Extra data (e.g., booking slots)")
    qualification_stage: str | None = Field(default=None, description="Current qualification stage")
    interest_score: int | None = Field(default=None, description="Current interest score (0-100)")
