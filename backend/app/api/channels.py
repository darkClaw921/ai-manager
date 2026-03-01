"""Channels API: CRUD for communication channels, test connection, webhook management."""

import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.repository import BaseRepository
from app.dependencies import EffectiveOwnerId, get_current_user, get_db
from app.models.booking import Booking
from app.models.channel import Channel, ChannelType
from app.models.conversation import Conversation, Message
from app.models.lead import Lead
from app.models.script import QualificationScript
from app.models.user import AdminUser
from app.schemas.channel import ChannelCreate, ChannelResponse, ChannelUpdate
from app.schemas.common import PaginatedResponse
from app.services.telegram_polling_service import TelegramPollingService
from app.services.telegram_webhook_service import TelegramWebhookService

logger = structlog.get_logger(__name__)

router = APIRouter()


async def _register_telegram_webhook(channel: Channel, db: AsyncSession) -> None:
    """Register a Telegram webhook for a channel and save the secret to config."""
    settings = get_settings()
    config = dict(channel.config or {})
    bot_token = config.get("bot_token", "")

    if not bot_token or not settings.WEBHOOK_BASE_URL:
        return

    webhook_secret = config.get("webhook_secret") or TelegramWebhookService.generate_webhook_secret()
    webhook_url = f"{settings.WEBHOOK_BASE_URL.rstrip('/')}/api/v1/webhooks/telegram/{channel.id}/update"

    service = TelegramWebhookService()
    try:
        result = await service.set_webhook(bot_token, webhook_url, webhook_secret)
        if result.get("ok"):
            config["webhook_secret"] = webhook_secret
            config["webhook_url"] = webhook_url
            channel.config = config
            logger.info("telegram_webhook_registered", channel_id=str(channel.id), url=webhook_url)
        else:
            logger.error("telegram_webhook_registration_failed", channel_id=str(channel.id), result=result)
    except Exception:
        logger.exception("telegram_webhook_registration_error", channel_id=str(channel.id))
    finally:
        await service.close()


async def _deregister_telegram_webhook(channel: Channel) -> None:
    """Remove Telegram webhook for a channel."""
    config = channel.config or {}
    bot_token = config.get("bot_token", "")

    if not bot_token:
        return

    service = TelegramWebhookService()
    try:
        await service.delete_webhook(bot_token)
        logger.info("telegram_webhook_deregistered", channel_id=str(channel.id))
    except Exception:
        logger.exception("telegram_webhook_deregistration_error", channel_id=str(channel.id))
    finally:
        await service.close()


async def _setup_telegram_channel(
    channel: Channel, db: AsyncSession, polling_service: TelegramPollingService
) -> None:
    """Set up a Telegram channel in the appropriate mode (webhook or polling)."""
    bot_mode = (channel.config or {}).get("bot_mode", "webhook")
    if bot_mode == "polling":
        bot_token = (channel.config or {}).get("bot_token", "")
        if bot_token:
            await polling_service.start_polling(channel.id, bot_token)
            logger.info("telegram_polling_started", channel_id=str(channel.id))
    else:
        await _register_telegram_webhook(channel, db)


async def _teardown_telegram_channel(
    channel: Channel, polling_service: TelegramPollingService
) -> None:
    """Tear down a Telegram channel (stop polling or deregister webhook)."""
    bot_mode = (channel.config or {}).get("bot_mode", "webhook")
    if bot_mode == "polling":
        await polling_service.stop_polling(channel.id)
        logger.info("telegram_polling_stopped", channel_id=str(channel.id))
    else:
        await _deregister_telegram_webhook(channel)


def _channel_response(channel: Channel) -> ChannelResponse:
    """Build a ChannelResponse from a Channel model, populating script name from relationship."""
    resp = ChannelResponse.model_validate(channel)
    if channel.qualification_script is not None:
        resp.qualification_script_name = channel.qualification_script.name
    else:
        resp.qualification_script_name = None
    return resp


async def _validate_script_id(db: AsyncSession, script_id: uuid.UUID | None) -> None:
    """Validate that the qualification script exists in the database."""
    if script_id is None:
        return
    result = await db.execute(select(QualificationScript).where(QualificationScript.id == script_id))
    if result.scalars().first() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Qualification script not found")


def _check_owner(channel: Channel, owner_id: uuid.UUID | None) -> None:
    """Check that the channel belongs to the effective owner. Raises 404 if not."""
    if owner_id is not None and channel.owner_id != owner_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")


@router.get("", response_model=PaginatedResponse[ChannelResponse])
async def list_channels(
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[AdminUser, Depends(get_current_user)],
    owner_id: EffectiveOwnerId,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[ChannelResponse]:
    """List all channels."""
    filters = []
    if owner_id is not None:
        filters.append(Channel.owner_id == owner_id)

    repo = BaseRepository(Channel, db)
    total = await repo.count(filters)
    offset = (page - 1) * page_size
    items = await repo.get_multi(
        offset=offset, limit=page_size, filters=filters, order_by=Channel.created_at.desc()
    )
    pages = (total + page_size - 1) // page_size if total > 0 else 1
    return PaginatedResponse(
        items=[_channel_response(item) for item in items],
        total=total,
        page=page,
        pages=pages,
    )


@router.post("", response_model=ChannelResponse, status_code=status.HTTP_201_CREATED)
async def create_channel(
    body: ChannelCreate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[AdminUser, Depends(get_current_user)],
) -> ChannelResponse:
    """Create a new channel. Auto-registers Telegram webhook or starts polling."""
    await _validate_script_id(db, body.qualification_script_id)

    repo = BaseRepository(Channel, db)
    channel = await repo.create(**body.model_dump(), owner_id=current_user.id)

    if channel.type == ChannelType.TELEGRAM and channel.is_active:
        await _setup_telegram_channel(channel, db, request.app.state.polling_service)

    return _channel_response(channel)


@router.get("/{channel_id}", response_model=ChannelResponse)
async def get_channel(
    channel_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[AdminUser, Depends(get_current_user)],
    owner_id: EffectiveOwnerId,
) -> ChannelResponse:
    """Get channel details."""
    repo = BaseRepository(Channel, db)
    channel = await repo.get(channel_id)
    if channel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")
    _check_owner(channel, owner_id)
    return _channel_response(channel)


@router.put("/{channel_id}", response_model=ChannelResponse)
async def update_channel(
    channel_id: uuid.UUID,
    body: ChannelUpdate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[AdminUser, Depends(get_current_user)],
    owner_id: EffectiveOwnerId,
) -> ChannelResponse:
    """Update a channel. Handles webhook/polling mode switching on config changes."""
    await _validate_script_id(db, body.qualification_script_id)

    repo = BaseRepository(Channel, db)
    channel = await repo.get(channel_id)
    if channel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")
    _check_owner(channel, owner_id)

    old_config = dict(channel.config or {})
    old_active = channel.is_active

    channel = await repo.update(channel, **body.model_dump(exclude_unset=True))

    # Handle mode/token/active changes for Telegram channels
    if channel.type == ChannelType.TELEGRAM:
        new_config = channel.config or {}
        polling_service: TelegramPollingService = request.app.state.polling_service

        old_mode = old_config.get("bot_mode", "webhook")
        new_mode = new_config.get("bot_mode", "webhook")
        token_changed = old_config.get("bot_token") != new_config.get("bot_token")
        active_changed = old_active != channel.is_active
        mode_changed = old_mode != new_mode

        if mode_changed or token_changed or active_changed:
            # Teardown old mode first (use old config for mode detection)
            old_channel_stub = Channel(
                id=channel.id,
                name=channel.name,
                type=channel.type,
                config=old_config,
                is_active=old_active,
            )
            await _teardown_telegram_channel(old_channel_stub, polling_service)

            # Setup new mode if channel is active
            if channel.is_active:
                await _setup_telegram_channel(channel, db, polling_service)

    return _channel_response(channel)


@router.delete("/{channel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_channel(
    channel_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[AdminUser, Depends(get_current_user)],
    owner_id: EffectiveOwnerId,
) -> None:
    """Delete a channel and all related data (conversations, messages, bookings, leads)."""
    repo = BaseRepository(Channel, db)
    channel = await repo.get(channel_id)
    if channel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")
    _check_owner(channel, owner_id)

    if channel.type == ChannelType.TELEGRAM:
        await _teardown_telegram_channel(channel, request.app.state.polling_service)

    # Cascade delete related entities in correct order
    # 1. Messages for conversations linked to this channel
    conv_ids_subq = select(Conversation.id).where(Conversation.channel_id == channel_id).scalar_subquery()
    await db.execute(delete(Message).where(Message.conversation_id.in_(conv_ids_subq)))

    # 2. Conversations linked to this channel
    await db.execute(delete(Conversation).where(Conversation.channel_id == channel_id))

    # 3. Bookings for leads linked to this channel
    lead_ids_subq = select(Lead.id).where(Lead.channel_id == channel_id).scalar_subquery()
    await db.execute(delete(Booking).where(Booking.lead_id.in_(lead_ids_subq)))

    # 4. Leads linked to this channel
    await db.execute(delete(Lead).where(Lead.channel_id == channel_id))

    # 5. The channel itself
    await repo.delete(channel)


@router.post("/{channel_id}/test", status_code=status.HTTP_200_OK)
async def test_channel_connection(
    channel_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[AdminUser, Depends(get_current_user)],
    owner_id: EffectiveOwnerId,
) -> dict:
    """Test channel connection by calling Telegram getMe API."""
    repo = BaseRepository(Channel, db)
    channel = await repo.get(channel_id)
    if channel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")
    _check_owner(channel, owner_id)

    config = channel.config or {}

    if channel.type == ChannelType.TELEGRAM:
        bot_token = config.get("bot_token", "")
        if not bot_token:
            return {"status": "error", "message": "Bot token не настроен"}

        service = TelegramWebhookService()
        try:
            result = await service.get_me(bot_token)
            if result.get("ok"):
                bot_info = result.get("result", {})
                bot_name = bot_info.get("first_name", "Unknown")
                bot_username = bot_info.get("username", "")
                return {
                    "status": "ok",
                    "message": f"Бот подключен: {bot_name} (@{bot_username})",
                }
            return {"status": "error", "message": result.get("description", "Ошибка проверки токена")}
        except Exception as exc:
            return {"status": "error", "message": f"Ошибка подключения: {exc}"}
        finally:
            await service.close()

    if channel.type == ChannelType.WEB_WIDGET:
        return {"status": "ok", "message": "Web widget канал готов"}

    return {"status": "ok", "message": "Конфигурация канала корректна"}
