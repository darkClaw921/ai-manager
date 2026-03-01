"""Service layer for lead management."""

import uuid

import structlog
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repository import BaseRepository
from app.models.lead import Lead, LeadStatus
from app.services.conversation_service import PaginatedResult

logger = structlog.get_logger(__name__)


class LeadService:
    """Business logic for leads and qualification data."""

    def __init__(self, db_session: AsyncSession) -> None:
        self._db = db_session
        self._repo = BaseRepository(Lead, db_session)

    async def get_or_create_lead(
        self,
        channel_id: uuid.UUID,
        external_id: str,
        name: str | None = None,
    ) -> Lead:
        """Get an existing lead by channel + external_id, or create a new one.

        The combination of channel_id + external_id uniquely identifies a lead
        from a specific channel (e.g., Telegram user ID, widget session ID).
        """
        result = await self._db.execute(
            select(Lead).where(
                Lead.channel_id == channel_id,
                Lead.external_id == external_id,
            )
        )
        lead = result.scalar_one_or_none()

        if lead:
            return lead

        return await self._repo.create(
            channel_id=channel_id,
            external_id=external_id,
            name=name,
            status=LeadStatus.NEW,
            qualification_stage="initial",
            qualification_data={},
            interest_score=0,
        )

    async def get_lead(self, lead_id: uuid.UUID) -> Lead | None:
        """Get a lead by ID."""
        return await self._repo.get(lead_id)

    async def update_lead(self, lead_id: uuid.UUID, **kwargs: Any) -> Lead | None:
        """Update lead fields.

        Args:
            lead_id: Lead UUID.
            **kwargs: Fields to update (name, phone, email, company, status, etc.).

        Returns:
            Updated Lead or None if not found.
        """
        lead = await self._repo.get(lead_id)
        if not lead:
            return None
        return await self._repo.update(lead, **kwargs)

    async def update_qualification(
        self,
        lead_id: uuid.UUID,
        stage: str,
        data: dict[str, Any],
        score: int,
    ) -> Lead | None:
        """Update lead qualification state.

        Args:
            lead_id: Lead UUID.
            stage: New qualification stage value.
            data: Updated qualification_data dict.
            score: New interest_score (0-100).

        Returns:
            Updated Lead or None if not found.
        """
        lead = await self._repo.get(lead_id)
        if not lead:
            return None

        lead.qualification_stage = stage
        lead.qualification_data = data
        lead.interest_score = score

        # Auto-update lead status based on stage
        if stage == "qualifying" or stage in {
            "needs_discovery",
            "budget_check",
            "timeline_check",
            "decision_maker",
        }:
            if lead.status == LeadStatus.NEW:
                lead.status = LeadStatus.QUALIFYING
        elif stage in {"qualified", "booking_offer"}:
            lead.status = LeadStatus.QUALIFIED

        await self._db.flush()
        return lead

    async def list_leads(
        self,
        filters: dict[str, Any] | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> PaginatedResult:
        """List leads with optional filters and pagination.

        Supported filters:
            - channel_id: UUID
            - status: LeadStatus
            - search: str (partial name match)
        """
        where_clauses = []
        if filters:
            if "channel_id" in filters:
                where_clauses.append(Lead.channel_id == filters["channel_id"])
            if "status" in filters:
                where_clauses.append(Lead.status == filters["status"])
            if "search" in filters and filters["search"]:
                where_clauses.append(Lead.name.ilike(f"%{filters['search']}%"))

        items = await self._repo.get_multi(
            offset=offset,
            limit=limit,
            filters=where_clauses,
            order_by=Lead.created_at.desc(),
        )
        total = await self._repo.count(filters=where_clauses)

        return PaginatedResult(items=items, total=total, offset=offset, limit=limit)
