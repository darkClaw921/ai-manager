"""Bookings API: CRUD for bookings and booking settings with owner_id scoping."""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repository import BaseRepository
from app.dependencies import EffectiveOwnerId, get_current_user, get_db
from app.models.booking import Booking, BookingSettings, BookingStatus
from app.models.channel import Channel
from app.models.lead import Lead
from app.models.user import AdminUser, UserRole
from app.schemas.booking import (
    BookingCreate,
    BookingResponse,
    BookingSettingsResponse,
    BookingSettingsUpdate,
    BookingUpdate,
)
from app.schemas.common import PaginatedResponse

router = APIRouter()


def _check_booking_owner(booking: Booking, owner_id: uuid.UUID | None) -> None:
    """Check that a booking belongs to the effective owner via Lead -> Channel chain."""
    if owner_id is None:
        return
    lead = booking.lead
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    channel = lead.channel
    if channel is None or channel.owner_id != owner_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")


@router.get("", response_model=PaginatedResponse[BookingResponse])
async def list_bookings(
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[AdminUser, Depends(get_current_user)],
    owner_id: EffectiveOwnerId,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: BookingStatus | None = Query(None, alias="status"),
    manager_id: uuid.UUID | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
) -> PaginatedResponse[BookingResponse]:
    """List bookings with filtering and pagination."""
    # Build query with owner_id filtering via Lead -> Channel double JOIN
    query = (
        select(Booking)
        .join(Lead, Booking.lead_id == Lead.id, isouter=True)
        .join(Channel, Lead.channel_id == Channel.id, isouter=True)
    )
    count_query = (
        select(func.count())
        .select_from(Booking)
        .join(Lead, Booking.lead_id == Lead.id, isouter=True)
        .join(Channel, Lead.channel_id == Channel.id, isouter=True)
    )

    filters = []
    if owner_id is not None:
        filters.append(Channel.owner_id == owner_id)
    if status_filter is not None:
        filters.append(Booking.status == status_filter)
    if manager_id is not None:
        filters.append(Booking.manager_id == manager_id)
    if date_from is not None:
        filters.append(Booking.scheduled_at >= date_from)
    if date_to is not None:
        filters.append(Booking.scheduled_at <= date_to)

    for f in filters:
        query = query.where(f)
        count_query = count_query.where(f)

    total = (await db.execute(count_query)).scalar_one()

    offset = (page - 1) * page_size
    query = query.order_by(Booking.scheduled_at.desc()).offset(offset).limit(page_size)
    result = await db.execute(query)
    items = list(result.scalars().all())

    pages = (total + page_size - 1) // page_size if total > 0 else 1
    return PaginatedResponse(
        items=[BookingResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        pages=pages,
    )


@router.post("", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
async def create_booking(
    body: BookingCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[AdminUser, Depends(get_current_user)],
) -> BookingResponse:
    """Create a new booking."""
    repo = BaseRepository(Booking, db)
    booking = await repo.create(**body.model_dump())
    return BookingResponse.model_validate(booking)


@router.put("/{booking_id}", response_model=BookingResponse)
async def update_booking(
    booking_id: uuid.UUID,
    body: BookingUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[AdminUser, Depends(get_current_user)],
    owner_id: EffectiveOwnerId,
) -> BookingResponse:
    """Update a booking (confirm, cancel, reschedule)."""
    repo = BaseRepository(Booking, db)
    booking = await repo.get(booking_id)
    if booking is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    _check_booking_owner(booking, owner_id)
    booking = await repo.update(booking, **body.model_dump(exclude_unset=True))
    return BookingResponse.model_validate(booking)


@router.get("/settings", response_model=list[BookingSettingsResponse])
async def get_booking_settings(
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[AdminUser, Depends(get_current_user)],
    owner_id: EffectiveOwnerId,
) -> list[BookingSettingsResponse]:
    """Get booking settings for managers (scoped by owner_id)."""
    # 1. Load managers — scoped if owner_id is set
    manager_query = select(AdminUser).where(
        AdminUser.role == UserRole.MANAGER,
        AdminUser.is_active.is_(True),
    )
    if owner_id is not None:
        manager_query = manager_query.where(AdminUser.id == owner_id)

    managers_result = await db.execute(manager_query)
    managers = {m.id: m for m in managers_result.scalars().all()}

    # 2. Load existing settings for these managers
    if owner_id is not None:
        settings_result = await db.execute(
            select(BookingSettings).where(BookingSettings.manager_id == owner_id)
        )
    else:
        settings_result = await db.execute(select(BookingSettings))
    existing = {s.manager_id: s for s in settings_result.scalars().all()}

    # 3. Auto-create missing settings for managers without them
    for mid in managers:
        if mid not in existing:
            new_settings = BookingSettings(manager_id=mid)
            db.add(new_settings)
            existing[mid] = new_settings
    await db.flush()

    # 4. Build response with manager_name
    result = []
    for settings in existing.values():
        resp = BookingSettingsResponse.model_validate(settings)
        manager = managers.get(settings.manager_id)
        resp.manager_name = manager.full_name if manager else None
        result.append(resp)
    return result


@router.put("/settings/{settings_id}", response_model=BookingSettingsResponse)
async def update_booking_settings(
    settings_id: uuid.UUID,
    body: BookingSettingsUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[AdminUser, Depends(get_current_user)],
    owner_id: EffectiveOwnerId,
) -> BookingSettingsResponse:
    """Update booking settings (scoped by owner_id via manager_id)."""
    repo = BaseRepository(BookingSettings, db)
    settings = await repo.get(settings_id)
    if settings is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking settings not found")

    # Scope check: manager can only edit their own settings
    if owner_id is not None and settings.manager_id != owner_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking settings not found")

    settings = await repo.update(settings, **body.model_dump(exclude_unset=True))
    return BookingSettingsResponse.model_validate(settings)
