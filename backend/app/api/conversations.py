"""Conversations API endpoints: list, get details with messages, update status, owner scoping."""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import structlog

from app.channels.telegram import TelegramAdapter
from app.channels.web_widget import WebWidgetAdapter
from app.db.repository import BaseRepository
from app.dependencies import EffectiveOwnerId, get_current_user, get_db, require_admin
from app.models.channel import Channel, ChannelType
from app.models.conversation import Conversation, ConversationStatus, Message, MessageRole
from app.models.user import AdminUser
from app.schemas.common import PaginatedResponse
from app.schemas.conversation import (
    ConversationDetailResponse,
    ConversationResponse,
    ConversationStatusUpdate,
    MessageResponse,
    SendManagerMessageRequest,
    SendManagerMessageResponse,
)

logger = structlog.get_logger(__name__)

router = APIRouter()

# Allowed status transitions
ALLOWED_TRANSITIONS: dict[ConversationStatus, set[ConversationStatus]] = {
    ConversationStatus.ACTIVE: {ConversationStatus.PAUSED, ConversationStatus.COMPLETED, ConversationStatus.HANDED_OFF},
    ConversationStatus.PAUSED: {ConversationStatus.ACTIVE, ConversationStatus.COMPLETED},
    ConversationStatus.HANDED_OFF: {ConversationStatus.ACTIVE, ConversationStatus.COMPLETED},
    ConversationStatus.COMPLETED: set(),
}


def _check_conversation_owner(conversation: Conversation, owner_id: uuid.UUID | None) -> None:
    """Check that a conversation belongs to the effective owner via its channel."""
    if owner_id is None:
        return
    channel = conversation.channel
    if channel is None or channel.owner_id != owner_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")


@router.get("", response_model=PaginatedResponse[ConversationResponse])
async def list_conversations(
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[AdminUser, Depends(get_current_user)],
    owner_id: EffectiveOwnerId,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: ConversationStatus | None = Query(None, alias="status"),
    lead_id: uuid.UUID | None = Query(None),
    channel_id: uuid.UUID | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
) -> PaginatedResponse[ConversationResponse]:
    """List conversations with filtering and pagination."""
    # Build query with owner_id filtering via Channel JOIN
    query = select(Conversation).join(Channel, Conversation.channel_id == Channel.id, isouter=True)
    count_query = select(func.count()).select_from(Conversation).join(Channel, Conversation.channel_id == Channel.id, isouter=True)

    filters = []
    if owner_id is not None:
        filters.append(Channel.owner_id == owner_id)
    if status_filter is not None:
        filters.append(Conversation.status == status_filter)
    if lead_id is not None:
        filters.append(Conversation.lead_id == lead_id)
    if channel_id is not None:
        filters.append(Conversation.channel_id == channel_id)
    if date_from is not None:
        filters.append(Conversation.created_at >= date_from)
    if date_to is not None:
        filters.append(Conversation.created_at <= date_to)

    for f in filters:
        query = query.where(f)
        count_query = count_query.where(f)

    total = (await db.execute(count_query)).scalar_one()

    offset = (page - 1) * page_size
    query = query.order_by(Conversation.created_at.desc()).offset(offset).limit(page_size)
    result = await db.execute(query)
    items = list(result.scalars().all())

    pages = (total + page_size - 1) // page_size if total > 0 else 1

    def _conv_response(item: Conversation) -> ConversationResponse:
        resp = ConversationResponse.model_validate(item)
        resp.manager_name = item.manager.full_name if item.manager else None
        return resp

    return PaginatedResponse(
        items=[_conv_response(item) for item in items],
        total=total,
        page=page,
        pages=pages,
    )


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[AdminUser, Depends(get_current_user)],
    owner_id: EffectiveOwnerId,
) -> ConversationDetailResponse:
    """Get conversation details with all messages."""
    result = await db.execute(
        select(Conversation)
        .options(selectinload(Conversation.messages), selectinload(Conversation.lead), selectinload(Conversation.channel), selectinload(Conversation.manager))
        .where(Conversation.id == conversation_id)
    )
    conversation = result.scalar_one_or_none()
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    _check_conversation_owner(conversation, owner_id)

    messages = [MessageResponse.model_validate(m) for m in conversation.messages]

    return ConversationDetailResponse(
        id=conversation.id,
        lead_id=conversation.lead_id,
        channel_id=conversation.channel_id,
        status=conversation.status,
        started_at=conversation.started_at,
        ended_at=conversation.ended_at,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        lead_name=conversation.lead.name if conversation.lead else None,
        channel_name=conversation.channel.name if conversation.channel else None,
        manager_id=conversation.manager_id,
        manager_name=conversation.manager.full_name if conversation.manager else None,
        message_count=len(messages),
        messages=messages,
    )


@router.put("/{conversation_id}/status", response_model=ConversationResponse)
async def update_conversation_status(
    conversation_id: uuid.UUID,
    body: ConversationStatusUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[AdminUser, Depends(get_current_user)],
    owner_id: EffectiveOwnerId,
) -> ConversationResponse:
    """Update conversation status (pause, complete, handoff)."""
    repo = BaseRepository(Conversation, db)
    conversation = await repo.get(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    _check_conversation_owner(conversation, owner_id)

    # Validate transition
    allowed = ALLOWED_TRANSITIONS.get(conversation.status, set())
    if body.status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Невозможно перейти из '{conversation.status.value}' в '{body.status.value}'",
        )

    update_kwargs: dict = {"status": body.status}

    if body.status == ConversationStatus.HANDED_OFF:
        update_kwargs["ended_at"] = datetime.utcnow()
        update_kwargs["manager_id"] = _current_user.id
        # System message: manager took over
        db.add(Message(
            conversation_id=conversation_id,
            role=MessageRole.SYSTEM,
            content=f"Менеджер {_current_user.full_name} взял диалог",
        ))

    elif body.status == ConversationStatus.COMPLETED:
        update_kwargs["ended_at"] = datetime.utcnow()

    elif body.status == ConversationStatus.ACTIVE and conversation.status == ConversationStatus.HANDED_OFF:
        update_kwargs["ended_at"] = None
        update_kwargs["manager_id"] = None
        # System message: manager returned to bot
        db.add(Message(
            conversation_id=conversation_id,
            role=MessageRole.SYSTEM,
            content="Менеджер вернул диалог боту",
        ))

    await db.flush()
    conversation = await repo.update(conversation, **update_kwargs)
    resp = ConversationResponse.model_validate(conversation)
    resp.manager_name = conversation.manager.full_name if conversation.manager else None
    return resp


@router.post("/{conversation_id}/messages", response_model=SendManagerMessageResponse)
async def send_manager_message(
    conversation_id: uuid.UUID,
    body: SendManagerMessageRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AdminUser, Depends(get_current_user)],
    owner_id: EffectiveOwnerId,
) -> SendManagerMessageResponse:
    """Send a message as a manager to the client."""
    # Load conversation with channel and lead
    result = await db.execute(
        select(Conversation)
        .options(selectinload(Conversation.channel), selectinload(Conversation.lead))
        .where(Conversation.id == conversation_id)
    )
    conversation = result.scalar_one_or_none()
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    _check_conversation_owner(conversation, owner_id)

    if conversation.status != ConversationStatus.HANDED_OFF:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Диалог не в режиме менеджера",
        )

    # Save the message
    message = Message(
        conversation_id=conversation.id,
        role=MessageRole.ASSISTANT,
        content=body.text,
        metadata_={
            "sender": "manager",
            "manager_id": str(current_user.id),
            "manager_name": current_user.full_name,
        },
    )
    db.add(message)
    await db.flush()

    # Deliver to client via the appropriate channel
    channel = conversation.channel
    lead = conversation.lead
    if channel and lead and lead.external_id:
        try:
            if channel.type == ChannelType.TELEGRAM:
                config = channel.config or {}
                adapter = TelegramAdapter(bot_token=config.get("bot_token", ""))
                try:
                    await adapter.send_message(lead.external_id, body.text)
                finally:
                    await adapter.close()
            elif channel.type == ChannelType.WEB_WIDGET:
                from app.api.ws_manager import manager as connection_manager

                adapter = WebWidgetAdapter(connection_manager)
                await adapter.send_message(lead.external_id, body.text)
        except Exception:
            logger.warning(
                "manager_message_delivery_failed",
                conversation_id=str(conversation_id),
                channel_type=channel.type.value if channel.type else None,
            )

    return SendManagerMessageResponse(
        id=message.id,
        content=message.content,
        created_at=message.created_at,
    )


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[AdminUser, Depends(require_admin)],
    owner_id: EffectiveOwnerId,
) -> None:
    """Delete a conversation and all its messages."""
    repo = BaseRepository(Conversation, db)
    conversation = await repo.get(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    _check_conversation_owner(conversation, owner_id)

    # Delete all messages first (no CASCADE configured)
    await db.execute(delete(Message).where(Message.conversation_id == conversation_id))

    await repo.delete(conversation)
