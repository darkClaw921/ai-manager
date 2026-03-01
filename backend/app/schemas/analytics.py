"""Analytics schemas: dashboard, lead stats, funnel."""

from typing import Any

from pydantic import BaseModel, Field


class DashboardResponse(BaseModel):
    """Dashboard summary statistics."""

    total_leads: int = 0
    leads_today: int = 0
    leads_week: int = 0
    leads_month: int = 0
    active_conversations: int = 0
    qualification_rate: float = 0.0
    bookings_count: int = 0
    avg_interest_score: float = 0.0


class LeadsByDay(BaseModel):
    """Leads count for a specific day."""

    date: str
    count: int


class LeadStatsResponse(BaseModel):
    """Lead statistics response."""

    leads_by_day: list[LeadsByDay] = Field(default_factory=list)
    leads_by_status: dict[str, int] = Field(default_factory=dict)
    leads_by_channel: dict[str, int] = Field(default_factory=dict)


class FunnelStage(BaseModel):
    """Funnel stage data."""

    stage: str
    count: int


class FunnelResponse(BaseModel):
    """Conversion funnel response."""

    stages: list[FunnelStage] = Field(default_factory=list)
