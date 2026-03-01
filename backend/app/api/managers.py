"""Managers API: list managers with stats, detailed statistics (admin only)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, require_admin
from app.models.channel import Channel
from app.models.conversation import Conversation, ConversationStatus
from app.models.lead import Lead, LeadStatus
from app.models.user import AdminUser, UserRole
from app.schemas.manager import ManagerDetailStats, ManagerWithStats

router = APIRouter()


@router.get("", response_model=list[ManagerWithStats])
async def list_managers(
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[AdminUser, Depends(require_admin)],
) -> list[ManagerWithStats]:
    """List all managers with aggregate counts (admin only).

    Returns managers sorted by created_at descending, each with:
    - channels_count: number of channels owned
    - leads_count: number of leads across owned channels
    - conversations_count: number of conversations across owned channels
    """
    # Subquery: count channels per manager
    channels_sq = (
        select(
            Channel.owner_id.label("owner_id"),
            func.count(Channel.id).label("cnt"),
        )
        .group_by(Channel.owner_id)
        .subquery()
    )

    # Subquery: count leads per manager (via channel.owner_id)
    leads_sq = (
        select(
            Channel.owner_id.label("owner_id"),
            func.count(Lead.id).label("cnt"),
        )
        .join(Lead, Lead.channel_id == Channel.id)
        .group_by(Channel.owner_id)
        .subquery()
    )

    # Subquery: count conversations per manager (via channel.owner_id)
    conversations_sq = (
        select(
            Channel.owner_id.label("owner_id"),
            func.count(Conversation.id).label("cnt"),
        )
        .join(Conversation, Conversation.channel_id == Channel.id)
        .group_by(Channel.owner_id)
        .subquery()
    )

    # Main query: select managers with left-joined counts
    stmt = (
        select(
            AdminUser,
            func.coalesce(channels_sq.c.cnt, 0).label("channels_count"),
            func.coalesce(leads_sq.c.cnt, 0).label("leads_count"),
            func.coalesce(conversations_sq.c.cnt, 0).label("conversations_count"),
        )
        .outerjoin(channels_sq, channels_sq.c.owner_id == AdminUser.id)
        .outerjoin(leads_sq, leads_sq.c.owner_id == AdminUser.id)
        .outerjoin(conversations_sq, conversations_sq.c.owner_id == AdminUser.id)
        .where(AdminUser.role == UserRole.MANAGER)
        .order_by(AdminUser.created_at.desc())
    )

    result = await db.execute(stmt)
    rows = result.all()

    managers = []
    for row in rows:
        user = row[0]
        managers.append(
            ManagerWithStats(
                id=user.id,
                email=user.email,
                full_name=user.full_name,
                is_active=user.is_active,
                created_at=user.created_at,
                channels_count=row[1],
                leads_count=row[2],
                conversations_count=row[3],
            )
        )

    return managers


@router.get("/{manager_id}/stats", response_model=ManagerDetailStats)
async def get_manager_stats(
    manager_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[AdminUser, Depends(require_admin)],
) -> ManagerDetailStats:
    """Get detailed statistics for a specific manager (admin only).

    Returns:
    - Manager info with aggregate counts
    - Leads grouped by status
    - Conversations grouped by status
    - Recent activity (last 10 leads)
    """
    # Fetch the manager
    result = await db.execute(
        select(AdminUser).where(
            AdminUser.id == manager_id,
            AdminUser.role == UserRole.MANAGER,
        )
    )
    manager = result.scalar_one_or_none()
    if manager is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Manager not found",
        )

    # Get channel IDs owned by this manager
    channel_ids_result = await db.execute(
        select(Channel.id).where(Channel.owner_id == manager_id)
    )
    channel_ids = [row[0] for row in channel_ids_result.all()]

    # Counts
    channels_count = len(channel_ids)

    if channel_ids:
        leads_count = (await db.execute(
            select(func.count()).select_from(Lead).where(Lead.channel_id.in_(channel_ids))
        )).scalar_one()

        conversations_count = (await db.execute(
            select(func.count()).select_from(Conversation).where(Conversation.channel_id.in_(channel_ids))
        )).scalar_one()

        # Leads by status
        leads_status_result = await db.execute(
            select(Lead.status, func.count().label("cnt"))
            .where(Lead.channel_id.in_(channel_ids))
            .group_by(Lead.status)
        )
        leads_by_status = {row.status.value: row.cnt for row in leads_status_result.all()}

        # Conversations by status
        conv_status_result = await db.execute(
            select(Conversation.status, func.count().label("cnt"))
            .where(Conversation.channel_id.in_(channel_ids))
            .group_by(Conversation.status)
        )
        conversations_by_status = {row.status.value: row.cnt for row in conv_status_result.all()}

        # Recent activity: last 10 leads
        recent_leads_result = await db.execute(
            select(Lead)
            .where(Lead.channel_id.in_(channel_ids))
            .order_by(Lead.created_at.desc())
            .limit(10)
        )
        recent_leads = recent_leads_result.scalars().all()
        recent_activity = [
            {
                "type": "lead",
                "id": str(lead.id),
                "name": lead.name or lead.external_id or "Unknown",
                "status": lead.status.value,
                "created_at": lead.created_at.isoformat() if lead.created_at else None,
            }
            for lead in recent_leads
        ]
    else:
        leads_count = 0
        conversations_count = 0
        leads_by_status = {}
        conversations_by_status = {}
        recent_activity = []

    manager_stats = ManagerWithStats(
        id=manager.id,
        email=manager.email,
        full_name=manager.full_name,
        is_active=manager.is_active,
        created_at=manager.created_at,
        channels_count=channels_count,
        leads_count=leads_count,
        conversations_count=conversations_count,
    )

    return ManagerDetailStats(
        manager=manager_stats,
        leads_by_status=leads_by_status,
        conversations_by_status=conversations_by_status,
        recent_activity=recent_activity,
    )
