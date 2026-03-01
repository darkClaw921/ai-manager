"""Analytics API: dashboard summary, lead stats, conversion funnel, CSV export.

Uses AnalyticsService for data retrieval with optional Redis caching.
All endpoints support owner_id scoping via EffectiveOwnerId dependency.
"""

import csv
import io
import uuid
from datetime import datetime, timezone
from typing import Annotated

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.dependencies import EffectiveOwnerId, get_current_user, get_db
from app.models.channel import Channel
from app.models.lead import Lead
from app.models.user import AdminUser
from app.schemas.analytics import DashboardResponse, FunnelResponse, FunnelStage, LeadStatsResponse, LeadsByDay
from app.services.analytics_service import AnalyticsService

router = APIRouter()


async def _get_redis():
    """Create an async Redis client (best-effort, returns None on failure)."""
    try:
        settings = get_settings()
        client = aioredis.from_url(settings.REDIS_URL)
        await client.ping()
        return client
    except Exception:
        return None


async def _get_analytics_service(db: AsyncSession) -> AnalyticsService:
    """Build AnalyticsService with DB session and optional Redis cache."""
    redis_client = await _get_redis()
    return AnalyticsService(db=db, redis_client=redis_client)


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[AdminUser, Depends(get_current_user)],
    owner_id: EffectiveOwnerId,
    period: str = Query("7d", pattern=r"^(7d|30d|90d|365d)$"),
) -> DashboardResponse:
    """Get dashboard summary statistics.

    Args:
        period: Time period for filtering (7d, 30d, 90d, 365d).
    """
    service = await _get_analytics_service(db)
    data = await service.get_dashboard(period=period, owner_id=owner_id)
    return DashboardResponse(**data)


@router.get("/leads", response_model=LeadStatsResponse)
async def get_lead_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[AdminUser, Depends(get_current_user)],
    owner_id: EffectiveOwnerId,
    days: int = Query(30, ge=1, le=365),
) -> LeadStatsResponse:
    """Get lead statistics: leads per day, by status, by channel.

    Args:
        days: Number of days to look back (1-365).
    """
    period_map = {7: "7d", 30: "30d", 90: "90d", 365: "365d"}
    # Find closest matching period
    period = "30d"
    for threshold, label in sorted(period_map.items()):
        if days <= threshold:
            period = label
            break

    service = await _get_analytics_service(db)
    data = await service.get_lead_stats(period=period, owner_id=owner_id)

    leads_by_day = [LeadsByDay(date=item["date"], count=item["count"]) for item in data.get("leads_by_day", [])]

    return LeadStatsResponse(
        leads_by_day=leads_by_day,
        leads_by_status=data.get("leads_by_status", {}),
        leads_by_channel=data.get("leads_by_channel", {}),
    )


@router.get("/funnel", response_model=FunnelResponse)
async def get_conversion_funnel(
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[AdminUser, Depends(get_current_user)],
    owner_id: EffectiveOwnerId,
) -> FunnelResponse:
    """Get conversion funnel data."""
    service = await _get_analytics_service(db)
    data = await service.get_conversion_funnel(owner_id=owner_id)

    stages = [
        FunnelStage(stage=s["stage"], count=s["count"])
        for s in data.get("stages", [])
    ]
    return FunnelResponse(stages=stages)


@router.get("/export")
async def export_leads_csv(
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[AdminUser, Depends(get_current_user)],
    owner_id: EffectiveOwnerId,
) -> StreamingResponse:
    """Export all leads as a CSV file (scoped by owner_id).

    Returns:
        StreamingResponse with CSV content.
    """
    query = select(Lead)
    if owner_id is not None:
        query = query.join(Channel, Lead.channel_id == Channel.id).where(
            Channel.owner_id == owner_id
        )
    query = query.order_by(Lead.created_at.desc())

    result = await db.execute(query)
    leads = list(result.scalars().all())

    output = io.StringIO()
    writer = csv.writer(output)

    # Header row
    writer.writerow([
        "ID",
        "Имя",
        "Email",
        "Телефон",
        "Компания",
        "Статус",
        "Interest Score",
        "Этап квалификации",
        "Источник",
        "Дата создания",
    ])

    # Data rows
    for lead in leads:
        writer.writerow([
            str(lead.id),
            lead.name or "",
            lead.email or "",
            lead.phone or "",
            lead.company or "",
            lead.status.value if lead.status else "",
            lead.interest_score,
            lead.qualification_stage or "",
            lead.source or "",
            lead.created_at.strftime("%Y-%m-%d %H:%M:%S") if lead.created_at else "",
        ])

    output.seek(0)

    now = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"leads_export_{now}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
