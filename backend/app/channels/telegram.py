"""Telegram channel adapter -- sends messages via Telegram Bot HTTP API.

Uses httpx for direct HTTP calls to the Telegram Bot API so that the backend
can push messages without depending on the python-telegram-bot library.
"""

import structlog
from datetime import datetime, timezone
from typing import Any

import httpx

from app.channels.base import AbstractChannelAdapter, IncomingMessage
from app.models.channel import ChannelType

logger = structlog.get_logger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org"


class TelegramAdapter(AbstractChannelAdapter):
    """Adapter for sending/receiving messages through Telegram Bot API.

    Uses direct HTTP POST to the Telegram Bot API via httpx, so the backend
    service does not depend on the python-telegram-bot library.
    """

    def __init__(self, bot_token: str) -> None:
        self._token = bot_token
        self._base_url = f"{TELEGRAM_API_BASE}/bot{bot_token}"
        self._client = httpx.AsyncClient(timeout=15.0)

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    # ------------------------------------------------------------------
    # AbstractChannelAdapter interface
    # ------------------------------------------------------------------

    async def send_message(self, external_id: str, text: str, **kwargs: Any) -> None:
        """Send a text message to a Telegram chat.

        Args:
            external_id: Telegram chat_id (as string).
            text: Message text (HTML formatting supported).
            **kwargs: Optional keys:
                - parse_mode (str): "HTML" | "MarkdownV2" (default: "HTML")
                - reply_markup (dict): Telegram InlineKeyboardMarkup dict
        """
        parse_mode = kwargs.get("parse_mode", "HTML")
        payload: dict[str, Any] = {
            "chat_id": external_id,
            "text": text,
            "parse_mode": parse_mode,
        }

        reply_markup = kwargs.get("reply_markup")
        if reply_markup:
            payload["reply_markup"] = reply_markup

        await self._api_request("sendMessage", payload)

    async def process_incoming(self, raw_data: dict) -> IncomingMessage:
        """Parse a Telegram Update dict into a unified IncomingMessage.

        Extracts chat_id, text, and user info from the Update object.

        Args:
            raw_data: Telegram Update as a dict (from webhook JSON body).

        Returns:
            IncomingMessage with normalized fields.
        """
        message = raw_data.get("message", {})
        chat = message.get("chat", {})
        from_user = message.get("from", {})

        external_id = str(chat.get("id", ""))
        text = message.get("text", "")
        timestamp_unix = message.get("date")

        timestamp = (
            datetime.fromtimestamp(timestamp_unix, tz=timezone.utc)
            if timestamp_unix
            else datetime.now(timezone.utc)
        )

        metadata: dict[str, Any] = {
            "telegram_user_id": from_user.get("id"),
            "username": from_user.get("username"),
            "first_name": from_user.get("first_name"),
            "last_name": from_user.get("last_name"),
            "language_code": from_user.get("language_code"),
            "message_id": message.get("message_id"),
        }

        return IncomingMessage(
            external_id=external_id,
            text=text,
            channel_type=ChannelType.TELEGRAM,
            metadata=metadata,
            timestamp=timestamp,
        )

    async def send_booking_prompt(
        self,
        external_id: str,
        available_slots: list,
    ) -> None:
        """Send an inline keyboard with available booking time slots.

        Each slot dict should have 'date' and 'time' keys. Buttons are arranged
        in rows of 2.

        Args:
            external_id: Telegram chat_id.
            available_slots: List of dicts like [{"date": "2026-03-01", "time": "10:00"}, ...].
        """
        if not available_slots:
            await self.send_message(
                external_id,
                "К сожалению, сейчас нет доступных слотов для записи. "
                "Попробуйте позже или уточните у менеджера.",
            )
            return

        # Build inline keyboard rows (2 buttons per row)
        buttons: list[list[dict[str, str]]] = []
        row: list[dict[str, str]] = []

        for slot in available_slots:
            slot_date = slot.get("date", "")
            slot_time = slot.get("time", "")
            label = f"{slot_date} {slot_time}"
            callback_data = f"book:{slot_date}:{slot_time}"

            row.append({"text": label, "callback_data": callback_data})
            if len(row) == 2:
                buttons.append(row)
                row = []

        if row:
            buttons.append(row)

        reply_markup = {"inline_keyboard": buttons}

        await self.send_message(
            external_id,
            "Выберите удобное время для консультации:",
            reply_markup=reply_markup,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _api_request(self, method: str, payload: dict[str, Any]) -> dict:
        """Make a POST request to the Telegram Bot API.

        Args:
            method: Telegram API method name (e.g., "sendMessage").
            payload: Request body as dict.

        Returns:
            Parsed JSON response dict.

        Raises:
            httpx.HTTPStatusError: On non-2xx response.
        """
        url = f"{self._base_url}/{method}"
        try:
            response = await self._client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            if not data.get("ok"):
                logger.error(
                    "Telegram API error for %s: %s",
                    method,
                    data.get("description", "unknown error"),
                )
            return data
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Telegram API HTTP error for %s: %s %s",
                method,
                exc.response.status_code,
                exc.response.text,
            )
            raise
        except httpx.RequestError as exc:
            logger.error("Telegram API request error for %s: %s", method, exc)
            raise
