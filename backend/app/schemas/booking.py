"""Booking and booking settings schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.booking import BookingMode, BookingStatus


class BookingCreate(BaseModel):
    """Create booking request."""

    lead_id: uuid.UUID = Field(..., description="Lead ID")
    manager_id: uuid.UUID | None = Field(None, description="Manager ID")
    scheduled_at: datetime = Field(..., description="Scheduled date/time")
    duration_minutes: int = Field(30, ge=15, le=120, description="Duration in minutes")
    status: BookingStatus = Field(default=BookingStatus.PENDING)
    meeting_link: str | None = Field(None, max_length=500)
    notes: str | None = None


class BookingUpdate(BaseModel):
    """Update booking request. All fields optional."""

    manager_id: uuid.UUID | None = None
    scheduled_at: datetime | None = None
    duration_minutes: int | None = Field(None, ge=15, le=120)
    status: BookingStatus | None = None
    meeting_link: str | None = Field(None, max_length=500)
    notes: str | None = None


class BookingResponse(BaseModel):
    """Booking response."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    lead_id: uuid.UUID
    manager_id: uuid.UUID | None = None
    scheduled_at: datetime
    duration_minutes: int
    status: BookingStatus
    meeting_link: str | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime | None = None


class BookingSettingsUpdate(BaseModel):
    """Update booking settings request."""

    available_days: list[int] | None = Field(None, description="Available weekdays (0=Mon, 6=Sun)")
    available_hours: dict[str, str] | None = Field(None, description="Start/end hours, e.g. {start: '09:00', end: '18:00'}")
    slot_duration: int | None = Field(None, ge=15, le=120, description="Slot duration in minutes")
    timezone: str | None = Field(None, max_length=100)
    booking_link: str | None = Field(None, max_length=500)
    booking_mode: BookingMode | None = None


class BookingSettingsResponse(BaseModel):
    """Booking settings response."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    manager_id: uuid.UUID
    available_days: list[int] | dict | None = None
    available_hours: dict[str, str] | None = None
    slot_duration: int = 30
    timezone: str = "Europe/Moscow"
    booking_link: str | None = None
    booking_mode: BookingMode
    manager_name: str | None = None
