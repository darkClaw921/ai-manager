"""Leads API endpoints: list, get, update, delete with owner_id scoping via Channel."""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repository import BaseRepository
from app.dependencies import EffectiveOwnerId, get_current_user, get_db, require_admin
from app.models.booking import Booking
from app.models.channel import Channel
from app.models.conversation import Conversation, Message
from app.models.lead import Lead, LeadStatus
from app.models.user import AdminUser
from app.schemas.common import PaginatedResponse
from app.ai.qualification import STAGE_LABELS, compute_score_breakdown
from app.models.script import QualificationScript
from app.schemas.lead import LeadResponse, LeadUpdateRequest, ScoreBreakdownItem

router = APIRouter()


def _lead_response(
    lead: Lead,
    script: QualificationScript | None = None,
    include_breakdown: bool = False,
) -> LeadResponse:
    """Build a LeadResponse with channel info, stage label, and optional breakdown.

    Args:
        lead: The Lead model instance.
        script: Optional QualificationScript for script name and score_config.
        include_breakdown: When True, compute score_breakdown. Set to False
            for list endpoints to keep responses lightweight.
    """
    response = LeadResponse.model_validate(lead)
    if lead.channel:
        response.channel_name = lead.channel.name
        response.channel_type = lead.channel.type.value if lead.channel.type else None

    # Always populate human-readable stage label
    if lead.qualification_stage:
        response.qualification_stage_label = STAGE_LABELS.get(
            lead.qualification_stage, lead.qualification_stage
        )

    if not include_breakdown:
        return response

    # Populate score breakdown and script name
    if script is not None:
        response.qualification_script_name = script.name
        response.score_breakdown = [
            ScoreBreakdownItem(**item)
            for item in compute_score_breakdown(
                lead.qualification_data, script.score_config
            )
        ]
    elif lead.qualification_data:
        response.score_breakdown = [
            ScoreBreakdownItem(**item)
            for item in compute_score_breakdown(lead.qualification_data, None)
        ]

    return response


async def _check_lead_owner(lead: Lead, owner_id: uuid.UUID | None) -> None:
    """Check that a lead belongs to the effective owner via its channel."""
    if owner_id is None:
        return
    # Lead's ownership is determined by its channel's owner_id
    channel = lead.channel
    if channel is None or channel.owner_id != owner_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")


@router.get("", response_model=PaginatedResponse[LeadResponse])
async def list_leads(
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[AdminUser, Depends(get_current_user)],
    owner_id: EffectiveOwnerId,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: LeadStatus | None = Query(None, alias="status"),
    channel_id: uuid.UUID | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    search: str | None = Query(None),
) -> PaginatedResponse[LeadResponse]:
    """List leads with filtering and pagination."""
    # Build query with owner_id filtering via Channel JOIN
    query = select(Lead).join(Channel, Lead.channel_id == Channel.id, isouter=True)
    count_query = select(func.count()).select_from(Lead).join(Channel, Lead.channel_id == Channel.id, isouter=True)

    filters = []
    if owner_id is not None:
        filters.append(Channel.owner_id == owner_id)
    if status_filter is not None:
        filters.append(Lead.status == status_filter)
    if channel_id is not None:
        filters.append(Lead.channel_id == channel_id)
    if date_from is not None:
        filters.append(Lead.created_at >= date_from)
    if date_to is not None:
        filters.append(Lead.created_at <= date_to)
    if search:
        search_pattern = f"%{search}%"
        filters.append(
            Lead.name.ilike(search_pattern)
            | Lead.email.ilike(search_pattern)
            | Lead.phone.ilike(search_pattern)
        )

    for f in filters:
        query = query.where(f)
        count_query = count_query.where(f)

    total = (await db.execute(count_query)).scalar_one()

    offset = (page - 1) * page_size
    query = query.order_by(Lead.created_at.desc()).offset(offset).limit(page_size)
    result = await db.execute(query)
    items = list(result.scalars().all())

    pages = (total + page_size - 1) // page_size if total > 0 else 1
    return PaginatedResponse(
        items=[_lead_response(item) for item in items],
        total=total,
        page=page,
        pages=pages,
    )


@router.get("/{lead_id}", response_model=LeadResponse)
async def get_lead(
    lead_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[AdminUser, Depends(get_current_user)],
    owner_id: EffectiveOwnerId,
) -> LeadResponse:
    """Get lead details by ID."""
    repo = BaseRepository(Lead, db)
    lead = await repo.get(lead_id)
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    await _check_lead_owner(lead, owner_id)

    # Load qualification script via channel relationship (selectin lazy loaded)
    script = lead.channel.qualification_script if lead.channel else None
    return _lead_response(lead, script=script, include_breakdown=True)


@router.put("/{lead_id}", response_model=LeadResponse)
async def update_lead(
    lead_id: uuid.UUID,
    body: LeadUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[AdminUser, Depends(get_current_user)],
    owner_id: EffectiveOwnerId,
) -> LeadResponse:
    """Update lead data."""
    repo = BaseRepository(Lead, db)
    lead = await repo.get(lead_id)
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    await _check_lead_owner(lead, owner_id)

    update_data = body.model_dump(exclude_unset=True)
    lead = await repo.update(lead, **update_data)
    return _lead_response(lead)


@router.delete("/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lead(
    lead_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[AdminUser, Depends(require_admin)],
    owner_id: EffectiveOwnerId,
) -> None:
    """Delete a lead and all related conversations, messages, and bookings."""
    repo = BaseRepository(Lead, db)
    lead = await repo.get(lead_id)
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    await _check_lead_owner(lead, owner_id)

    # Delete messages for all conversations of this lead
    conversation_ids = [c.id for c in (lead.conversations or [])]
    if conversation_ids:
        await db.execute(delete(Message).where(Message.conversation_id.in_(conversation_ids)))
        await db.execute(delete(Conversation).where(Conversation.lead_id == lead_id))

    # Delete bookings
    await db.execute(delete(Booking).where(Booking.lead_id == lead_id))

    await repo.delete(lead)
