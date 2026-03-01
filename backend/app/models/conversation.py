import enum
import uuid
from datetime import datetime

from sqlalchemy import Enum, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class ConversationStatus(str, enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    HANDED_OFF = "handed_off"


class MessageRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class MessageType(str, enum.Enum):
    TEXT = "text"
    BUTTON = "button"
    BOOKING_LINK = "booking_link"


class Conversation(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "conversations"

    lead_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("leads.id"), index=True)
    channel_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("channels.id"))
    status: Mapped[ConversationStatus] = mapped_column(
        Enum(ConversationStatus, values_callable=lambda e: [x.value for x in e]),
        default=ConversationStatus.ACTIVE,
        index=True,
    )
    started_at: Mapped[datetime | None] = mapped_column()
    ended_at: Mapped[datetime | None] = mapped_column()
    manager_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True, default=None
    )

    # Relationships
    lead = relationship("Lead", back_populates="conversations")
    channel = relationship("Channel", lazy="selectin")
    messages = relationship("Message", back_populates="conversation", lazy="selectin", order_by="Message.created_at")
    manager = relationship("AdminUser", lazy="selectin")


class Message(UUIDMixin, Base):
    __tablename__ = "messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversations.id"), index=True)
    role: Mapped[MessageRole] = mapped_column(
        Enum(MessageRole, values_callable=lambda e: [x.value for x in e]),
    )
    content: Mapped[str] = mapped_column(Text)
    message_type: Mapped[MessageType] = mapped_column(
        Enum(MessageType, values_callable=lambda e: [x.value for x in e]),
        default=MessageType.TEXT,
    )
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")
