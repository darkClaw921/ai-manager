"""Service layer for conversations and messages."""

import uuid

import structlog
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repository import BaseRepository
from app.models.conversation import (
    Conversation,
    ConversationStatus,
    Message,
    MessageRole,
    MessageType,
)

logger = structlog.get_logger(__name__)


@dataclass
class PaginatedResult:
    """Paginated query result."""

    items: list
    total: int
    offset: int
    limit: int


class ConversationService:
    """Business logic for conversations and messages."""

    def __init__(self, db_session: AsyncSession) -> None:
        self._db = db_session
        self._repo = BaseRepository(Conversation, db_session)
        self._msg_repo = BaseRepository(Message, db_session)

    async def get_or_create_conversation(
        self,
        lead_id: uuid.UUID,
        channel_id: uuid.UUID,
    ) -> Conversation:
        """Get an active or handed-off conversation for the lead/channel, or create a new one.

        Only returns an existing conversation if its status is ACTIVE or HANDED_OFF.
        """
        result = await self._db.execute(
            select(Conversation).where(
                Conversation.lead_id == lead_id,
                Conversation.channel_id == channel_id,
                Conversation.status.in_([ConversationStatus.ACTIVE, ConversationStatus.HANDED_OFF]),
            )
        )
        conversation = result.scalar_one_or_none()

        if conversation:
            return conversation

        return await self._repo.create(
            lead_id=lead_id,
            channel_id=channel_id,
            status=ConversationStatus.ACTIVE,
            started_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )

    async def get_conversation(self, conversation_id: uuid.UUID) -> Conversation | None:
        """Get a conversation by ID."""
        return await self._repo.get(conversation_id)

    async def get_messages(
        self,
        conversation_id: uuid.UUID,
        limit: int = 50,
    ) -> list[Message]:
        """Get the most recent messages for a conversation, ordered by created_at."""
        result = await self._db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        messages = list(result.scalars().all())
        # Return in chronological order
        messages.reverse()
        return messages

    async def add_message(
        self,
        conversation_id: uuid.UUID,
        role: MessageRole | str,
        content: str,
        message_type: MessageType | str = MessageType.TEXT,
        metadata: dict[str, Any] | None = None,
    ) -> Message:
        """Add a new message to a conversation."""
        if isinstance(role, str):
            role = MessageRole(role)
        if isinstance(message_type, str):
            message_type = MessageType(message_type)

        return await self._msg_repo.create(
            conversation_id=conversation_id,
            role=role,
            content=content,
            message_type=message_type,
            metadata_=metadata or {},
        )

    async def update_status(
        self,
        conversation_id: uuid.UUID,
        status: ConversationStatus | str,
    ) -> Conversation | None:
        """Update a conversation's status."""
        if isinstance(status, str):
            status = ConversationStatus(status)

        conversation = await self._repo.get(conversation_id)
        if not conversation:
            return None

        conversation.status = status
        if status in {ConversationStatus.COMPLETED, ConversationStatus.HANDED_OFF}:
            conversation.ended_at = datetime.now(timezone.utc).replace(tzinfo=None)

        await self._db.flush()
        return conversation

    async def list_conversations(
        self,
        filters: dict[str, Any] | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> PaginatedResult:
        """List conversations with optional filters and pagination.

        Supported filters:
            - lead_id: UUID
            - channel_id: UUID
            - status: ConversationStatus
        """
        where_clauses = []
        if filters:
            if "lead_id" in filters:
                where_clauses.append(Conversation.lead_id == filters["lead_id"])
            if "channel_id" in filters:
                where_clauses.append(Conversation.channel_id == filters["channel_id"])
            if "status" in filters:
                where_clauses.append(Conversation.status == filters["status"])

        items = await self._repo.get_multi(
            offset=offset,
            limit=limit,
            filters=where_clauses,
            order_by=Conversation.created_at.desc(),
        )
        total = await self._repo.count(filters=where_clauses)

        return PaginatedResult(items=items, total=total, offset=offset, limit=limit)
