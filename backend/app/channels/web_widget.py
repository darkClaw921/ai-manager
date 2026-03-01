"""Web widget channel adapter.

Implements the AbstractChannelAdapter for the embeddable chat widget.
Primary transport: WebSocket. Falls back to REST if the connection is down.
"""

import structlog
from datetime import datetime, timezone
from typing import Any

from app.api.ws_manager import ConnectionManager
from app.channels.base import AbstractChannelAdapter, IncomingMessage
from app.models.channel import ChannelType

logger = structlog.get_logger(__name__)


class WebWidgetAdapter(AbstractChannelAdapter):
    """Channel adapter for the web chat widget.

    Uses the ConnectionManager to send messages over WebSocket.
    session_id is used as external_id for widget users.
    """

    def __init__(self, connection_manager: ConnectionManager) -> None:
        self._manager = connection_manager

    async def send_message(self, external_id: str, text: str, **kwargs: Any) -> None:
        """Send a text message to the widget user via WebSocket.

        If the user is not connected, the message is logged as undelivered.
        In production, undelivered messages should be queued for later delivery.

        Args:
            external_id: Widget session_id.
            text: Message text to send.
            **kwargs: Optional keys: message_type (str), data (dict).
        """
        message_type = kwargs.get("message_type", "message")
        data = kwargs.get("data", {})

        payload: dict[str, Any] = {
            "type": message_type,
            "text": text,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        sent = await self._manager.send_message(external_id, payload)
        if not sent:
            logger.warning(
                "Widget message not delivered (session offline): session=%s text=%s...",
                external_id,
                text[:50],
            )

    async def process_incoming(self, raw_data: dict) -> IncomingMessage:
        """Parse a raw WebSocket JSON message into an IncomingMessage.

        Expected format:
            {
                "type": "message",
                "text": "...",
                "session_id": "uuid-string"
            }

        Args:
            raw_data: JSON dict received from the WebSocket.

        Returns:
            IncomingMessage with channel_type=WEB_WIDGET.
        """
        session_id = raw_data.get("session_id", "")
        text = raw_data.get("text", "")
        timestamp_str = raw_data.get("timestamp")

        timestamp = datetime.now(timezone.utc)
        if timestamp_str:
            try:
                timestamp = datetime.fromisoformat(timestamp_str)
            except (ValueError, TypeError):
                pass

        metadata = {
            k: v
            for k, v in raw_data.items()
            if k not in ("type", "text", "session_id", "timestamp")
        }

        return IncomingMessage(
            external_id=session_id,
            text=text,
            channel_type=ChannelType.WEB_WIDGET,
            metadata=metadata,
            timestamp=timestamp,
        )

    async def send_booking_prompt(
        self,
        external_id: str,
        available_slots: list,
    ) -> None:
        """Send a booking prompt with available time slots.

        Sends a special 'booking' message type containing the list of slots.

        Args:
            external_id: Widget session_id.
            available_slots: List of slot dicts with date/time info.
        """
        payload: dict[str, Any] = {
            "type": "booking",
            "text": "Выберите удобное время для консультации:",
            "data": {"slots": available_slots},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        sent = await self._manager.send_message(external_id, payload)
        if not sent:
            logger.warning(
                "Booking prompt not delivered (session offline): session=%s",
                external_id,
            )

    async def send_typing(self, external_id: str) -> bool:
        """Send a typing indicator to the widget user.

        Args:
            external_id: Widget session_id.

        Returns:
            True if the typing event was sent successfully.
        """
        return await self._manager.send_typing(external_id)
