"""Abstract channel adapter -- base interface for all communication channels.

All channels (Telegram, web widget, etc.) implement this interface to provide
a unified way for the ConversationEngine to send and receive messages.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.models.channel import ChannelType


@dataclass
class IncomingMessage:
    """Unified incoming message from any channel.

    Attributes:
        external_id: User identifier in the channel (e.g., Telegram user ID, widget session ID).
        text: Message text content.
        channel_type: Type of the originating channel.
        metadata: Additional channel-specific data.
        timestamp: When the message was received.
    """

    external_id: str
    text: str
    channel_type: ChannelType
    metadata: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class AbstractChannelAdapter(ABC):
    """Base interface for channel adapters.

    Each channel (Telegram, web widget) implements this to normalize
    message sending/receiving for the AI engine.
    """

    @abstractmethod
    async def send_message(self, external_id: str, text: str, **kwargs) -> None:
        """Send a text message to a user in the channel.

        Args:
            external_id: User identifier in the channel.
            text: Message text to send.
            **kwargs: Channel-specific options (e.g., buttons, formatting).
        """

    @abstractmethod
    async def process_incoming(self, raw_data: dict) -> IncomingMessage:
        """Parse raw channel data into a unified IncomingMessage.

        Args:
            raw_data: Raw JSON/dict from the channel webhook or WebSocket.

        Returns:
            IncomingMessage with normalized fields.
        """

    @abstractmethod
    async def send_booking_prompt(
        self,
        external_id: str,
        available_slots: list,
    ) -> None:
        """Send a booking prompt with available time slots.

        Args:
            external_id: User identifier in the channel.
            available_slots: List of available booking slots (dicts with date, time, etc.).
        """
