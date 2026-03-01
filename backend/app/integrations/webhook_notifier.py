"""Webhook notifier: fire-and-forget notifications via HTTP webhooks and Telegram.

Sends event notifications (new lead, qualified lead, booking, handoff) to:
  - A configured webhook URL (JSON POST)
  - A Telegram chat via Bot API

Errors in notifications never block the main application flow.
"""

import structlog
from datetime import datetime, timezone
from typing import Any

import httpx

logger = structlog.get_logger(__name__)

TIMEOUT_SECONDS = 10


class WebhookNotifier:
    """Send notifications about key events via webhook and/or Telegram.

    Args:
        webhook_url: HTTP endpoint for webhook notifications. None to disable.
        telegram_chat_id: Telegram chat ID for bot notifications. None to disable.
        telegram_bot_token: Telegram bot token. Required if telegram_chat_id is set.
        admin_base_url: Base URL of the admin panel for links in notifications.
        enabled_events: Set of event names to notify about. None means all events.
    """

    def __init__(
        self,
        webhook_url: str | None = None,
        telegram_chat_id: str | None = None,
        telegram_bot_token: str | None = None,
        admin_base_url: str = "http://localhost:3000",
        enabled_events: set[str] | None = None,
    ) -> None:
        self.webhook_url = webhook_url
        self.telegram_chat_id = telegram_chat_id
        self.telegram_bot_token = telegram_bot_token
        self.admin_base_url = admin_base_url
        self.enabled_events = enabled_events
        self._client = httpx.AsyncClient(timeout=TIMEOUT_SECONDS)

    def _is_event_enabled(self, event: str) -> bool:
        """Check if a specific event type should trigger notifications."""
        if self.enabled_events is None:
            return True
        return event in self.enabled_events

    async def notify_new_lead(self, lead_data: dict[str, Any]) -> None:
        """Notify about a new lead creation.

        Args:
            lead_data: Dict with id, name, email, phone, channel_type fields.
        """
        if not self._is_event_enabled("new_lead"):
            return

        name = lead_data.get("name") or "Неизвестный"
        channel = lead_data.get("channel_type") or "unknown"
        lead_id = lead_data.get("id", "")

        text = (
            f"Новый лид: {name}\n"
            f"Канал: {channel}\n"
            f"Email: {lead_data.get('email') or '-'}\n"
            f"Телефон: {lead_data.get('phone') or '-'}"
        )
        link = f"{self.admin_base_url}/leads"

        telegram_text = (
            f"<b>Новый лид</b>\n"
            f"Имя: {name}\n"
            f"Канал: {channel}\n"
            f"Email: {lead_data.get('email') or '-'}\n"
            f"Телефон: {lead_data.get('phone') or '-'}\n"
            f'<a href="{link}">Открыть в админке</a>'
        )

        await self._send_all(
            event="new_lead",
            text=text,
            telegram_text=telegram_text,
            payload={"event": "new_lead", "lead_id": str(lead_id), "data": lead_data},
        )

    async def notify_qualified_lead(self, lead_data: dict[str, Any]) -> None:
        """Notify about a lead being qualified.

        Args:
            lead_data: Dict with id, name, interest_score, status, qualification_stage fields.
        """
        if not self._is_event_enabled("qualified_lead"):
            return

        name = lead_data.get("name") or "Неизвестный"
        score = lead_data.get("interest_score", 0)
        lead_id = lead_data.get("id", "")

        text = (
            f"Квалифицированный лид: {name} (score: {score})\n"
            f"Этап: {lead_data.get('qualification_stage', '-')}\n"
            f"Статус: {lead_data.get('status', '-')}"
        )
        link = f"{self.admin_base_url}/leads"

        telegram_text = (
            f"<b>Квалифицированный лид</b>\n"
            f"Имя: {name}\n"
            f"Score: {score}\n"
            f"Этап: {lead_data.get('qualification_stage', '-')}\n"
            f'<a href="{link}">Открыть в админке</a>'
        )

        await self._send_all(
            event="qualified_lead",
            text=text,
            telegram_text=telegram_text,
            payload={"event": "qualified_lead", "lead_id": str(lead_id), "data": lead_data},
        )

    async def notify_booking(self, booking_data: dict[str, Any]) -> None:
        """Notify about a new booking (consultation appointment).

        Args:
            booking_data: Dict with id, lead_name, scheduled_at, duration_minutes fields.
        """
        if not self._is_event_enabled("booking"):
            return

        lead_name = booking_data.get("lead_name") or "Неизвестный"
        scheduled = booking_data.get("scheduled_at", "")
        duration = booking_data.get("duration_minutes", 30)

        text = (
            f"Новая запись на консультацию: {lead_name}\n"
            f"Дата: {scheduled}\n"
            f"Длительность: {duration} мин."
        )
        link = f"{self.admin_base_url}/bookings"

        telegram_text = (
            f"<b>Новая запись</b>\n"
            f"Клиент: {lead_name}\n"
            f"Дата: {scheduled}\n"
            f"Длительность: {duration} мин.\n"
            f'<a href="{link}">Открыть в админке</a>'
        )

        await self._send_all(
            event="booking",
            text=text,
            telegram_text=telegram_text,
            payload={"event": "booking", "data": booking_data},
        )

    async def notify_handoff(self, conversation_data: dict[str, Any]) -> None:
        """Notify about a conversation being handed off to a human manager.

        Args:
            conversation_data: Dict with id, lead_name, lead_id fields.
        """
        if not self._is_event_enabled("handoff"):
            return

        lead_name = conversation_data.get("lead_name") or "Неизвестный"
        conv_id = conversation_data.get("id", "")

        text = (
            f"Передача менеджеру: {lead_name}\n"
            f"Диалог: {str(conv_id)[:8]}..."
        )
        link = f"{self.admin_base_url}/conversations/{conv_id}"

        telegram_text = (
            f"<b>Передача менеджеру</b>\n"
            f"Клиент: {lead_name}\n"
            f'<a href="{link}">Открыть диалог</a>'
        )

        await self._send_all(
            event="handoff",
            text=text,
            telegram_text=telegram_text,
            payload={"event": "handoff", "conversation_id": str(conv_id), "data": conversation_data},
        )

    async def _send_all(
        self,
        event: str,
        text: str,
        telegram_text: str,
        payload: dict[str, Any],
    ) -> None:
        """Send notification to all configured channels (fire-and-forget).

        Errors are logged but never raised.
        """
        if self.webhook_url:
            await self._send_webhook(payload)

        if self.telegram_chat_id and self.telegram_bot_token:
            await self._send_telegram(telegram_text)

    async def _send_webhook(self, payload: dict[str, Any]) -> None:
        """POST JSON payload to the webhook URL."""
        try:
            payload["timestamp"] = datetime.now(timezone.utc).isoformat()
            response = await self._client.post(self.webhook_url, json=payload)
            logger.info(
                "Webhook notification sent: event=%s status=%d",
                payload.get("event"),
                response.status_code,
            )
        except Exception:
            logger.exception("Failed to send webhook notification: %s", payload.get("event"))

    async def _send_telegram(self, text: str) -> None:
        """Send HTML message to the configured Telegram chat."""
        try:
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
            response = await self._client.post(
                url,
                json={
                    "chat_id": self.telegram_chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
            )
            logger.info(
                "Telegram notification sent: chat_id=%s status=%d",
                self.telegram_chat_id,
                response.status_code,
            )
        except Exception:
            logger.exception("Failed to send Telegram notification to chat %s", self.telegram_chat_id)

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()
