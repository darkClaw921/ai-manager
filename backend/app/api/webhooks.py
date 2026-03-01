"""Webhook endpoints for Telegram channel.

Handles both:
- Legacy endpoints called by the separate telegram-bot service (/init, /message)
- Direct Telegram Update receiver (/update) — Telegram sends raw updates here
"""

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models.channel import Channel, ChannelType
from app.models.conversation import ConversationStatus, MessageRole
from app.models.lead import Lead
from app.rate_limit import limiter
from app.services.conversation_service import ConversationService
from app.services.lead_service import LeadService
from app.services.telegram_update_handler import TelegramUpdateHandler, build_engine

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class TelegramInitRequest(BaseModel):
    """Request body for initializing a Telegram conversation."""

    external_id: str = Field(..., description="Telegram chat_id")
    name: str | None = Field(default=None, description="User display name")


class TelegramInitResponse(BaseModel):
    """Response for conversation init."""

    conversation_id: str
    lead_id: str
    greeting: str


class TelegramMessageRequest(BaseModel):
    """Request body for processing a Telegram message."""

    external_id: str = Field(..., description="Telegram chat_id")
    text: str = Field(..., min_length=1, description="User message text")


class TelegramMessageResponse(BaseModel):
    """Response for a processed message."""

    text: str
    actions: list[dict] = Field(default_factory=list)
    qualification_stage: str | None = None
    interest_score: int = 0


class ConversationStatusResponse(BaseModel):
    """Response for conversation status."""

    conversation_id: str
    status: str
    lead_id: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_active_channel(
    db: AsyncSession,
    channel_id: uuid.UUID,
) -> Channel:
    """Fetch and validate the channel.

    Raises HTTPException 404 if channel does not exist or is not a Telegram channel.
    Raises HTTPException 403 if channel is inactive.
    """
    result = await db.execute(select(Channel).where(Channel.id == channel_id))
    channel = result.scalar_one_or_none()

    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    if channel.type != ChannelType.TELEGRAM:
        raise HTTPException(status_code=404, detail="Channel is not a Telegram channel")

    if not channel.is_active:
        raise HTTPException(status_code=403, detail="Channel is inactive")

    return channel


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/telegram/{channel_id}/init",
    response_model=TelegramInitResponse,
    summary="Initialize Telegram conversation",
)
@limiter.limit("60/minute")
async def telegram_init(
    request: Request,
    channel_id: uuid.UUID,
    body: TelegramInitRequest,
    db: AsyncSession = Depends(get_db),
) -> TelegramInitResponse:
    """Create or retrieve a conversation for a Telegram user.

    - Creates or finds an existing Lead by external_id + channel_id
    - Creates or finds an active Conversation
    - Calls ConversationEngine.start_conversation() if new
    - Returns conversation_id, lead_id, and greeting
    """
    channel = await _get_active_channel(db, channel_id)

    lead_service = LeadService(db_session=db)
    conversation_service = ConversationService(db_session=db)

    lead = await lead_service.get_or_create_lead(
        channel_id=channel.id,
        external_id=body.external_id,
        name=body.name,
    )

    # Check if there is already an active conversation
    conversation = await conversation_service.get_or_create_conversation(
        lead_id=lead.id,
        channel_id=channel.id,
    )

    # If the conversation was just created (no messages), generate greeting
    messages = await conversation_service.get_messages(conversation.id, limit=1)
    if not messages:
        engine = await build_engine(db)
        _conversation_id, greeting = await engine.start_conversation(
            lead_id=lead.id,
            channel_id=channel.id,
        )
    else:
        greeting = messages[0].content if messages else "Здравствуйте! Чем могу помочь?"

    return TelegramInitResponse(
        conversation_id=str(conversation.id),
        lead_id=str(lead.id),
        greeting=greeting,
    )


@router.post(
    "/telegram/{channel_id}",
    response_model=TelegramMessageResponse,
    summary="Process Telegram message",
)
@limiter.limit("60/minute")
async def telegram_message(
    request: Request,
    channel_id: uuid.UUID,
    body: TelegramMessageRequest,
    db: AsyncSession = Depends(get_db),
) -> TelegramMessageResponse:
    """Process a user message through the AI engine.

    - Finds the Lead by external_id + channel_id
    - Finds the active Conversation
    - Passes the message to ConversationEngine.process_message()
    - Returns the AI response with actions and qualification metadata
    """
    channel = await _get_active_channel(db, channel_id)

    lead_service = LeadService(db_session=db)
    conversation_service = ConversationService(db_session=db)

    # Find existing lead
    result = await db.execute(
        select(Lead).where(
            Lead.channel_id == channel.id,
            Lead.external_id == body.external_id,
        )
    )
    lead = result.scalar_one_or_none()

    if not lead:
        # Auto-create lead if not found (user may have skipped /start)
        lead = await lead_service.get_or_create_lead(
            channel_id=channel.id,
            external_id=body.external_id,
        )

    # Get or create active conversation
    conversation = await conversation_service.get_or_create_conversation(
        lead_id=lead.id,
        channel_id=channel.id,
    )

    # AI gate: save message but skip AI when manager handles the conversation
    if conversation.status == ConversationStatus.HANDED_OFF:
        await conversation_service.add_message(
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content=body.text,
        )
        return TelegramMessageResponse(
            text="",
            actions=[],
            qualification_stage=None,
            interest_score=0,
        )

    # Process through AI engine
    engine = await build_engine(db)
    engine_response = await engine.process_message(
        conversation_id=conversation.id,
        user_message=body.text,
    )

    return TelegramMessageResponse(
        text=engine_response.text,
        actions=[
            {"name": action.name, "details": action.details}
            for action in engine_response.actions
        ],
        qualification_stage=engine_response.qualification_stage.value,
        interest_score=engine_response.interest_score,
    )


@router.get(
    "/telegram/conversations/{conversation_id}/status",
    response_model=ConversationStatusResponse,
    summary="Get conversation status",
)
async def telegram_conversation_status(
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ConversationStatusResponse:
    """Get the current status of a conversation."""
    conversation_service = ConversationService(db_session=db)
    conversation = await conversation_service.get_conversation(conversation_id)

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return ConversationStatusResponse(
        conversation_id=str(conversation.id),
        status=conversation.status.value,
        lead_id=str(conversation.lead_id) if conversation.lead_id else None,
    )


# ---------------------------------------------------------------------------
# Direct Telegram Update receiver (no separate bot service needed)
# ---------------------------------------------------------------------------


@router.post(
    "/telegram/{channel_id}/update",
    summary="Receive raw Telegram Update",
)
@limiter.limit("120/minute")
async def telegram_update(
    request: Request,
    channel_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Receive a raw Telegram Update and process it.

    This endpoint is called directly by Telegram (no separate bot service needed).
    Validates the secret token from X-Telegram-Bot-Api-Secret-Token header.
    """
    # Fetch channel
    channel = await _get_active_channel(db, channel_id)
    config = channel.config or {}

    # Validate secret token
    expected_secret = config.get("webhook_secret", "")
    received_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not expected_secret or received_secret != expected_secret:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    bot_token = config.get("bot_token", "")
    if not bot_token:
        raise HTTPException(status_code=500, detail="Bot token not configured")

    update = await request.json()

    handler = TelegramUpdateHandler()
    await handler.handle_update(channel, update, db)

    return {"ok": True}
