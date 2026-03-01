"""Analytics service: dashboard summary, lead stats, conversion funnel.

Uses SQLAlchemy aggregations and optional Redis caching (TTL: 60s).
Supports owner_id scoping: when owner_id is provided, all queries are filtered
through Channel.owner_id via appropriate JOINs.
"""

import json
import uuid
from datetime import datetime, timedelta, timezone

import structlog
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking
from app.models.channel import Channel
from app.models.conversation import Conversation, ConversationStatus
from app.models.lead import Lead, LeadStatus

logger = structlog.get_logger(__name__)

# Cache TTL in seconds
CACHE_TTL = 60

# Period mapping: string -> timedelta
PERIOD_MAP = {
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
    "90d": timedelta(days=90),
    "365d": timedelta(days=365),
}


class AnalyticsService:
    """Service for analytics queries with optional Redis caching.

    Args:
        db: Async SQLAlchemy session.
        redis_client: Optional async Redis client for caching. If None, caching is skipped.
    """

    def __init__(self, db: AsyncSession, redis_client: Any = None) -> None:
        self._db = db
        self._redis = redis_client

    async def _get_cached(self, key: str) -> dict | None:
        """Try to get cached data from Redis."""
        if self._redis is None:
            return None
        try:
            data = await self._redis.get(key)
            if data:
                return json.loads(data)
        except Exception:
            logger.debug("Redis cache miss for %s", key)
        return None

    async def _set_cached(self, key: str, data: dict, ttl: int = CACHE_TTL) -> None:
        """Store data in Redis cache."""
        if self._redis is None:
            return
        try:
            await self._redis.set(key, json.dumps(data, default=str), ex=ttl)
        except Exception:
            logger.debug("Failed to set Redis cache for %s", key)

    def _cache_key_suffix(self, owner_id: uuid.UUID | None) -> str:
        """Build a cache key suffix based on owner_id."""
        return f":owner={owner_id}" if owner_id else ":global"

    async def get_dashboard(
        self, period: str = "7d", owner_id: uuid.UUID | None = None
    ) -> dict[str, Any]:
        """Get dashboard summary statistics.

        Args:
            period: Period filter (7d, 30d, 90d, 365d).
            owner_id: If set, scope all stats to this manager's data.

        Returns:
            Dict with total_leads, leads_today, leads_week, leads_month,
            active_conversations, qualification_rate, bookings_count,
            avg_interest_score.
        """
        cache_key = f"analytics:dashboard:{period}{self._cache_key_suffix(owner_id)}"
        cached = await self._get_cached(cache_key)
        if cached:
            return cached

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=today_start.weekday())
        month_start = today_start.replace(day=1)

        db = self._db

        # Base lead query with optional owner scoping
        def _lead_count_query():
            q = select(func.count()).select_from(Lead)
            if owner_id is not None:
                q = q.join(Channel, Lead.channel_id == Channel.id).where(
                    Channel.owner_id == owner_id
                )
            return q

        total_leads = (await db.execute(_lead_count_query())).scalar_one()

        leads_today = (await db.execute(
            _lead_count_query().where(Lead.created_at >= today_start)
        )).scalar_one()

        leads_week = (await db.execute(
            _lead_count_query().where(Lead.created_at >= week_start)
        )).scalar_one()

        leads_month = (await db.execute(
            _lead_count_query().where(Lead.created_at >= month_start)
        )).scalar_one()

        # Active conversations count
        conv_query = select(func.count()).select_from(Conversation).where(
            Conversation.status == ConversationStatus.ACTIVE
        )
        if owner_id is not None:
            conv_query = conv_query.join(Channel, Conversation.channel_id == Channel.id).where(
                Channel.owner_id == owner_id
            )
        active_conversations = (await db.execute(conv_query)).scalar_one()

        # Qualification rate
        qualified_query = _lead_count_query().where(
            Lead.status.in_([
                LeadStatus.QUALIFIED,
                LeadStatus.BOOKED,
                LeadStatus.HANDED_OFF,
            ])
        )
        qualified_count = (await db.execute(qualified_query)).scalar_one()
        qualification_rate = round(qualified_count / total_leads * 100, 1) if total_leads > 0 else 0.0

        # Bookings count (through Lead -> Channel)
        bookings_query = select(func.count()).select_from(Booking)
        if owner_id is not None:
            bookings_query = (
                bookings_query
                .join(Lead, Booking.lead_id == Lead.id)
                .join(Channel, Lead.channel_id == Channel.id)
                .where(Channel.owner_id == owner_id)
            )
        bookings_count = (await db.execute(bookings_query)).scalar_one()

        # Average interest score
        avg_query = select(func.avg(Lead.interest_score)).where(Lead.interest_score > 0)
        if owner_id is not None:
            avg_query = avg_query.join(Channel, Lead.channel_id == Channel.id).where(
                Channel.owner_id == owner_id
            )
        avg_score_result = (await db.execute(avg_query)).scalar_one()
        avg_interest_score = round(float(avg_score_result), 1) if avg_score_result else 0.0

        result = {
            "total_leads": total_leads,
            "leads_today": leads_today,
            "leads_week": leads_week,
            "leads_month": leads_month,
            "active_conversations": active_conversations,
            "qualification_rate": qualification_rate,
            "bookings_count": bookings_count,
            "avg_interest_score": avg_interest_score,
        }

        await self._set_cached(cache_key, result)
        return result

    async def get_lead_stats(
        self, period: str = "30d", owner_id: uuid.UUID | None = None
    ) -> dict[str, Any]:
        """Get lead statistics grouped by day, status, and channel.

        Args:
            period: Period filter (7d, 30d, 90d, 365d).
            owner_id: If set, scope all stats to this manager's data.

        Returns:
            Dict with leads_by_day, leads_by_status, leads_by_channel.
        """
        cache_key = f"analytics:lead_stats:{period}{self._cache_key_suffix(owner_id)}"
        cached = await self._get_cached(cache_key)
        if cached:
            return cached

        delta = PERIOD_MAP.get(period, timedelta(days=30))
        start_date = datetime.now(timezone.utc).replace(tzinfo=None) - delta
        db = self._db

        # Leads by day
        day_query = (
            select(
                func.date(Lead.created_at).label("day"),
                func.count().label("count"),
            )
            .where(Lead.created_at >= start_date)
        )
        if owner_id is not None:
            day_query = day_query.join(Channel, Lead.channel_id == Channel.id).where(
                Channel.owner_id == owner_id
            )
        day_query = day_query.group_by(func.date(Lead.created_at)).order_by(func.date(Lead.created_at))
        day_result = await db.execute(day_query)
        leads_by_day = [{"date": str(row.day), "count": row.count} for row in day_result.all()]

        # Leads by status
        status_query = select(Lead.status, func.count().label("count"))
        if owner_id is not None:
            status_query = status_query.join(Channel, Lead.channel_id == Channel.id).where(
                Channel.owner_id == owner_id
            )
        status_query = status_query.group_by(Lead.status)
        status_result = await db.execute(status_query)
        leads_by_status = {row.status.value: row.count for row in status_result.all()}

        # Leads by channel (resolve channel names)
        channel_query = (
            select(
                Channel.name,
                func.count().label("count"),
            )
            .join(Lead, Lead.channel_id == Channel.id, isouter=True)
        )
        if owner_id is not None:
            channel_query = channel_query.where(Channel.owner_id == owner_id)
        channel_query = channel_query.group_by(Channel.name)
        channel_result = await db.execute(channel_query)
        leads_by_channel = {}
        for row in channel_result.all():
            name = row.name if row.name else "Неизвестный"
            leads_by_channel[name] = row.count

        # Count leads with no channel (only in global scope)
        if owner_id is None:
            no_channel_count = (await db.execute(
                select(func.count()).select_from(Lead).where(Lead.channel_id.is_(None))
            )).scalar_one()
            if no_channel_count > 0:
                leads_by_channel["Без канала"] = no_channel_count

        result = {
            "leads_by_day": leads_by_day,
            "leads_by_status": leads_by_status,
            "leads_by_channel": leads_by_channel,
        }

        await self._set_cached(cache_key, result)
        return result

    async def get_conversion_funnel(
        self, owner_id: uuid.UUID | None = None
    ) -> dict[str, Any]:
        """Get conversion funnel data.

        Args:
            owner_id: If set, scope all stats to this manager's data.

        Returns:
            Dict with stages list, each containing name, count, and percentage.
        """
        cache_key = f"analytics:funnel{self._cache_key_suffix(owner_id)}"
        cached = await self._get_cached(cache_key)
        if cached:
            return cached

        db = self._db
        stages = [
            ("new", LeadStatus.NEW),
            ("qualifying", LeadStatus.QUALIFYING),
            ("qualified", LeadStatus.QUALIFIED),
            ("booked", LeadStatus.BOOKED),
            ("handed_off", LeadStatus.HANDED_OFF),
        ]

        # Total leads for percentage calculation
        total_query = select(func.count()).select_from(Lead)
        if owner_id is not None:
            total_query = total_query.join(Channel, Lead.channel_id == Channel.id).where(
                Channel.owner_id == owner_id
            )
        total_leads = (await db.execute(total_query)).scalar_one()

        funnel_stages = []
        for name, lead_status in stages:
            # Count leads that have reached this status or further
            idx = [s[1] for s in stages].index(lead_status)
            statuses_at_or_past = [s[1] for s in stages[idx:]]

            count_query = select(func.count()).select_from(Lead).where(
                Lead.status.in_(statuses_at_or_past)
            )
            if owner_id is not None:
                count_query = count_query.join(Channel, Lead.channel_id == Channel.id).where(
                    Channel.owner_id == owner_id
                )
            count = (await db.execute(count_query)).scalar_one()

            percentage = round(count / total_leads * 100, 1) if total_leads > 0 else 0.0
            funnel_stages.append({
                "stage": name,
                "count": count,
                "percentage": percentage,
            })

        result = {"stages": funnel_stages}

        await self._set_cached(cache_key, result)
        return result

    async def get_avg_response_time(self) -> float:
        """Get average AI response time in seconds.

        Calculated from message timestamps (difference between user and next assistant message).

        Returns:
            Average response time in seconds.
        """
        cache_key = "analytics:avg_response_time"
        cached = await self._get_cached(cache_key)
        if cached:
            return cached.get("avg_response_time", 0.0)

        # This is an approximation - in production, you'd log response times explicitly
        # For now, return 0 as we don't have timing data in messages
        result = {"avg_response_time": 0.0}
        await self._set_cached(cache_key, result)
        return 0.0

    async def get_qualification_breakdown(
        self, owner_id: uuid.UUID | None = None
    ) -> dict[str, int]:
        """Get lead distribution by qualification stage.

        Args:
            owner_id: If set, scope to this manager's data.

        Returns:
            Dict mapping qualification_stage -> count.
        """
        cache_key = f"analytics:qualification_breakdown{self._cache_key_suffix(owner_id)}"
        cached = await self._get_cached(cache_key)
        if cached:
            return cached

        db = self._db
        query = (
            select(
                Lead.qualification_stage,
                func.count().label("count"),
            )
            .where(Lead.qualification_stage.isnot(None))
        )
        if owner_id is not None:
            query = query.join(Channel, Lead.channel_id == Channel.id).where(
                Channel.owner_id == owner_id
            )
        query = query.group_by(Lead.qualification_stage)
        result = await db.execute(query)

        breakdown = {row.qualification_stage: row.count for row in result.all()}
        await self._set_cached(cache_key, breakdown)
        return breakdown
