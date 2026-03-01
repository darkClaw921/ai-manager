"""Lead schemas: response, update, filter."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.lead import LeadStatus


class ScoreBreakdownItem(BaseModel):
    """Single stage breakdown entry for interest score calculation."""

    stage_id: str
    stage_label: str
    weight: int
    completed: bool
    collected_info: str | None = None


class LeadResponse(BaseModel):
    """Lead response schema."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    channel_id: uuid.UUID | None = None
    external_id: str | None = None
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    company: str | None = None
    status: LeadStatus
    qualification_stage: str | None = None
    qualification_data: dict[str, Any] | None = None
    interest_score: int = 0
    source: str | None = None
    channel_name: str | None = None
    channel_type: str | None = None
    score_breakdown: list[ScoreBreakdownItem] | None = None
    qualification_script_name: str | None = None
    qualification_stage_label: str | None = None
    created_at: datetime
    updated_at: datetime | None = None


class LeadUpdateRequest(BaseModel):
    """Update lead request. All fields optional."""

    name: str | None = None
    phone: str | None = None
    email: str | None = None
    company: str | None = None
    status: LeadStatus | None = None
    qualification_stage: str | None = None
    qualification_data: dict[str, Any] | None = None
    interest_score: int | None = Field(None, ge=0, le=100)
    source: str | None = None


class LeadFilter(BaseModel):
    """Lead filter parameters."""

    status: LeadStatus | None = None
    channel_id: uuid.UUID | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    search: str | None = None
