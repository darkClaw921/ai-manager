"""Tests for ConversationService."""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import ConversationStatus, MessageRole
from app.services.conversation_service import ConversationService


class TestConversationServiceGetOrCreate:
    """Tests for ConversationService.get_or_create_conversation()."""

    @pytest.mark.asyncio
    async def test_creates_new_conversation(
        self, db_session: AsyncSession, lead_factory, channel_factory
    ):
        channel = await channel_factory()
        lead = await lead_factory(channel=channel)
        service = ConversationService(db_session=db_session)

        conv = await service.get_or_create_conversation(
            lead_id=lead.id, channel_id=channel.id,
        )

        assert conv is not None
        assert conv.lead_id == lead.id
        assert conv.channel_id == channel.id
        assert conv.status == ConversationStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_returns_existing_active_conversation(
        self, db_session: AsyncSession, lead_factory, channel_factory
    ):
        channel = await channel_factory()
        lead = await lead_factory(channel=channel)
        service = ConversationService(db_session=db_session)

        conv1 = await service.get_or_create_conversation(
            lead_id=lead.id, channel_id=channel.id,
        )
        conv2 = await service.get_or_create_conversation(
            lead_id=lead.id, channel_id=channel.id,
        )

        assert conv1.id == conv2.id

    @pytest.mark.asyncio
    async def test_creates_new_when_existing_completed(
        self, db_session: AsyncSession, lead_factory, channel_factory, conversation_factory
    ):
        channel = await channel_factory()
        lead = await lead_factory(channel=channel)
        # Create a completed conversation
        await conversation_factory(lead=lead, channel=channel, status=ConversationStatus.COMPLETED)

        service = ConversationService(db_session=db_session)
        conv = await service.get_or_create_conversation(
            lead_id=lead.id, channel_id=channel.id,
        )

        assert conv.status == ConversationStatus.ACTIVE


class TestConversationServiceMessages:
    """Tests for message operations."""

    @pytest.mark.asyncio
    async def test_add_message(
        self, db_session: AsyncSession, conversation_factory
    ):
        conv = await conversation_factory()
        service = ConversationService(db_session=db_session)

        msg = await service.add_message(
            conversation_id=conv.id,
            role=MessageRole.USER,
            content="Hello",
        )

        assert msg is not None
        assert msg.content == "Hello"
        assert msg.role == MessageRole.USER

    @pytest.mark.asyncio
    async def test_add_message_with_string_role(
        self, db_session: AsyncSession, conversation_factory
    ):
        conv = await conversation_factory()
        service = ConversationService(db_session=db_session)

        msg = await service.add_message(
            conversation_id=conv.id,
            role="assistant",
            content="Hi there",
        )

        assert msg.role == MessageRole.ASSISTANT

    @pytest.mark.asyncio
    async def test_get_messages(
        self, db_session: AsyncSession, conversation_factory, message_factory
    ):
        conv = await conversation_factory()
        await message_factory(conversation=conv, content="msg1", role=MessageRole.USER)
        await message_factory(conversation=conv, content="msg2", role=MessageRole.ASSISTANT)

        service = ConversationService(db_session=db_session)
        messages = await service.get_messages(conv.id)

        assert len(messages) == 2

    @pytest.mark.asyncio
    async def test_get_messages_empty(
        self, db_session: AsyncSession, conversation_factory
    ):
        conv = await conversation_factory()
        service = ConversationService(db_session=db_session)

        messages = await service.get_messages(conv.id)
        assert messages == []


class TestConversationServiceStatus:
    """Tests for status updates."""

    @pytest.mark.asyncio
    async def test_update_status(
        self, db_session: AsyncSession, conversation_factory
    ):
        conv = await conversation_factory()
        service = ConversationService(db_session=db_session)

        updated = await service.update_status(conv.id, ConversationStatus.PAUSED)
        assert updated is not None
        assert updated.status == ConversationStatus.PAUSED

    @pytest.mark.asyncio
    async def test_update_status_completed_sets_ended_at(
        self, db_session: AsyncSession, conversation_factory
    ):
        conv = await conversation_factory()
        service = ConversationService(db_session=db_session)

        updated = await service.update_status(conv.id, ConversationStatus.COMPLETED)
        assert updated.ended_at is not None

    @pytest.mark.asyncio
    async def test_update_status_handed_off_sets_ended_at(
        self, db_session: AsyncSession, conversation_factory
    ):
        conv = await conversation_factory()
        service = ConversationService(db_session=db_session)

        updated = await service.update_status(conv.id, ConversationStatus.HANDED_OFF)
        assert updated.ended_at is not None

    @pytest.mark.asyncio
    async def test_update_status_with_string(
        self, db_session: AsyncSession, conversation_factory
    ):
        conv = await conversation_factory()
        service = ConversationService(db_session=db_session)

        updated = await service.update_status(conv.id, "paused")
        assert updated.status == ConversationStatus.PAUSED

    @pytest.mark.asyncio
    async def test_update_status_not_found(self, db_session: AsyncSession):
        service = ConversationService(db_session=db_session)
        result = await service.update_status(uuid.uuid4(), ConversationStatus.PAUSED)
        assert result is None


class TestConversationServiceList:
    """Tests for list operations."""

    @pytest.mark.asyncio
    async def test_list_empty(self, db_session: AsyncSession):
        service = ConversationService(db_session=db_session)
        result = await service.list_conversations()
        assert result.total == 0

    @pytest.mark.asyncio
    async def test_list_with_conversations(
        self, db_session: AsyncSession, conversation_factory
    ):
        await conversation_factory()
        await conversation_factory()
        service = ConversationService(db_session=db_session)

        result = await service.list_conversations()
        assert result.total == 2

    @pytest.mark.asyncio
    async def test_list_with_status_filter(
        self, db_session: AsyncSession, conversation_factory
    ):
        await conversation_factory(status=ConversationStatus.ACTIVE)
        await conversation_factory(status=ConversationStatus.COMPLETED)
        service = ConversationService(db_session=db_session)

        result = await service.list_conversations(
            filters={"status": ConversationStatus.ACTIVE}
        )
        assert result.total == 1
