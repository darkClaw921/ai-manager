"""Conversation and message schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.conversation import ConversationStatus, MessageRole, MessageType


class MessageResponse(BaseModel):
    """Message response schema."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    conversation_id: uuid.UUID
    role: MessageRole
    content: str
    message_type: MessageType
    metadata_: dict | None = None
    created_at: datetime


class ConversationResponse(BaseModel):
    """Conversation response schema (list view)."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    lead_id: uuid.UUID
    channel_id: uuid.UUID
    status: ConversationStatus
    started_at: datetime | None = None
    ended_at: datetime | None = None
    created_at: datetime
    updated_at: datetime | None = None
    manager_id: uuid.UUID | None = None
    manager_name: str | None = None


class ConversationDetailResponse(BaseModel):
    """Conversation detail response with messages."""

    id: uuid.UUID
    lead_id: uuid.UUID
    channel_id: uuid.UUID
    status: ConversationStatus
    started_at: datetime | None = None
    ended_at: datetime | None = None
    created_at: datetime
    updated_at: datetime | None = None
    lead_name: str | None = None
    channel_name: str | None = None
    manager_id: uuid.UUID | None = None
    manager_name: str | None = None
    message_count: int = 0
    messages: list[MessageResponse] = []


class ConversationStatusUpdate(BaseModel):
    """Update conversation status."""

    status: ConversationStatus


class ConversationFilter(BaseModel):
    """Conversation filter parameters."""

    status: ConversationStatus | None = None
    lead_id: uuid.UUID | None = None
    channel_id: uuid.UUID | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None


class SendManagerMessageRequest(BaseModel):
    """Request to send a message as a manager."""

    text: str = Field(..., min_length=1)


class SendManagerMessageResponse(BaseModel):
    """Response after sending a manager message."""

    id: uuid.UUID
    content: str
    created_at: datetime
