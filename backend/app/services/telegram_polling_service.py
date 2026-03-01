"""Telegram long-polling service.

Manages per-channel asyncio tasks that continuously fetch updates via
``getUpdates`` and route them through :class:`TelegramUpdateHandler`.
"""

from __future__ import annotations

import asyncio
import uuid

import structlog
from sqlalchemy import select

from app.db.session import async_session_factory
from app.models.channel import Channel
from app.services.telegram_update_handler import TelegramUpdateHandler
from app.services.telegram_webhook_service import TelegramWebhookService

logger = structlog.get_logger(__name__)

# Backoff constants
_BACKOFF_BASE: float = 5.0
_BACKOFF_CAP: float = 60.0

# How often (in loop iterations) to check channel.is_active in the DB
_ACTIVE_CHECK_INTERVAL: int = 10


class TelegramPollingService:
    """Manages long-polling tasks for Telegram channels.

    A single instance lives in ``app.state.polling_service`` for the entire
    application lifetime.  Each channel gets its own :class:`asyncio.Task`
    running :meth:`_polling_loop`.
    """

    def __init__(self) -> None:
        self._tasks: dict[uuid.UUID, asyncio.Task] = {}
        self._handler = TelegramUpdateHandler()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start_polling(
        self,
        channel_id: uuid.UUID,
        bot_token: str,
    ) -> None:
        """Start (or restart) polling for a channel.

        If a polling task already exists for *channel_id* it is cancelled
        first.  The Telegram webhook is deleted before polling begins
        (Telegram requires this).

        Args:
            channel_id: UUID of the channel to poll.
            bot_token: Telegram bot token used for API calls.
        """
        # Cancel existing task if any
        if channel_id in self._tasks:
            await self.stop_polling(channel_id)

        # Delete webhook -- Telegram requires no active webhook for getUpdates
        wh_service = TelegramWebhookService()
        try:
            await wh_service.delete_webhook(bot_token)
            logger.info(
                "webhook_deleted_for_polling",
                channel_id=str(channel_id),
            )
        except Exception:
            logger.warning(
                "webhook_delete_failed",
                channel_id=str(channel_id),
                exc_info=True,
            )
        finally:
            await wh_service.close()

        # Create and store the polling task
        task = asyncio.create_task(
            self._polling_loop(channel_id, bot_token),
            name=f"polling-{channel_id}",
        )
        self._tasks[channel_id] = task
        logger.info(
            "polling_started",
            channel_id=str(channel_id),
        )

    async def stop_polling(self, channel_id: uuid.UUID) -> None:
        """Stop the polling task for a channel.

        Args:
            channel_id: UUID of the channel whose polling task to cancel.
        """
        task = self._tasks.pop(channel_id, None)
        if task is None:
            return

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        logger.info("polling_stopped", channel_id=str(channel_id))

    async def stop_all(self) -> None:
        """Cancel all active polling tasks (used during shutdown)."""
        channel_ids = list(self._tasks.keys())
        for channel_id in channel_ids:
            await self.stop_polling(channel_id)
        logger.info("all_polling_stopped", count=len(channel_ids))

    # ------------------------------------------------------------------
    # Internal polling loop
    # ------------------------------------------------------------------

    async def _polling_loop(
        self,
        channel_id: uuid.UUID,
        bot_token: str,
    ) -> None:
        """Infinite loop that fetches and processes updates for one channel.

        The loop uses long-polling (30 s server-side timeout) and implements
        exponential backoff on errors (5 s -> 10 s -> 20 s -> 40 s -> 60 s cap).
        Every ``_ACTIVE_CHECK_INTERVAL`` iterations the channel's ``is_active``
        flag is verified in the database -- if ``False`` the loop exits.
        """
        offset: int | None = None
        backoff_delay: float = _BACKOFF_BASE
        iteration: int = 0

        log = logger.bind(channel_id=str(channel_id))
        log.info("polling_loop_started")

        try:
            while True:
                wh_service = TelegramWebhookService()
                try:
                    # --- Periodic active-check ---
                    iteration += 1
                    if iteration % _ACTIVE_CHECK_INTERVAL == 0:
                        if not await self._is_channel_active(channel_id):
                            log.info("channel_deactivated_stopping_poll")
                            return

                    # --- Fetch updates ---
                    response = await wh_service.get_updates(
                        bot_token,
                        offset=offset,
                        timeout=30,
                    )

                    updates: list[dict] = response.get("result", [])

                    # --- Process each update ---
                    for update in updates:
                        update_id = update.get("update_id")
                        try:
                            await self._process_update(channel_id, update)
                        except Exception:
                            log.exception(
                                "update_processing_error",
                                update_id=update_id,
                            )

                        # Advance offset past this update
                        if update_id is not None:
                            offset = update_id + 1

                    # Reset backoff on success
                    backoff_delay = _BACKOFF_BASE

                except asyncio.CancelledError:
                    raise  # re-raise so the outer handler catches it
                except Exception:
                    log.exception(
                        "polling_error",
                        backoff=backoff_delay,
                    )
                    await asyncio.sleep(backoff_delay)
                    backoff_delay = min(backoff_delay * 2, _BACKOFF_CAP)
                finally:
                    await wh_service.close()

        except asyncio.CancelledError:
            log.info("polling_loop_cancelled")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _process_update(
        self,
        channel_id: uuid.UUID,
        update: dict,
    ) -> None:
        """Open a fresh DB session and delegate to the update handler."""
        async with async_session_factory() as session:
            channel = await session.get(Channel, channel_id)
            if channel is None:
                logger.warning(
                    "channel_not_found_during_poll",
                    channel_id=str(channel_id),
                )
                return
            await self._handler.handle_update(channel, update, session)
            await session.commit()

    @staticmethod
    async def _is_channel_active(channel_id: uuid.UUID) -> bool:
        """Check if the channel is still active in the database."""
        async with async_session_factory() as session:
            result = await session.execute(
                select(Channel.is_active).where(Channel.id == channel_id),
            )
            row = result.scalar_one_or_none()
            return bool(row)
