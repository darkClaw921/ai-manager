"""Telegram Update handler -- shared by webhook and polling modes.

Extracts update-processing logic from webhooks.py so that both the webhook
endpoint and the polling service can route incoming Telegram Updates through
the same code path.
"""

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.context_builder import ContextBuilder
from app.ai.embeddings import EmbeddingsManager
from app.ai.engine import ConversationEngine
from app.ai.rag import RAGPipeline
from app.ai.tools import ToolHandler
from app.channels.telegram import TelegramAdapter
from app.config import get_settings
from app.models.channel import Channel
from app.models.conversation import ConversationStatus, MessageRole
from app.services.conversation_service import ConversationService
from app.services.lead_service import LeadService
from app.services.telegram_webhook_service import TelegramWebhookService

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Module-level helper
# ---------------------------------------------------------------------------


async def build_engine(db: AsyncSession) -> ConversationEngine:
    """Create a ConversationEngine wired with all dependencies.

    This is a standalone async factory used by both the update handler
    and legacy endpoints in webhooks.py.

    The engine uses db_session to create per-owner LLM clients dynamically
    based on channel.owner_id, determined during context building.
    """
    settings = get_settings()

    from qdrant_client import AsyncQdrantClient

    qdrant_client = AsyncQdrantClient(
        host=settings.QDRANT_HOST,
        port=settings.QDRANT_PORT,
    )
    embeddings = EmbeddingsManager.get_instance()
    rag_pipeline = RAGPipeline(qdrant_client=qdrant_client, embeddings_manager=embeddings)

    context_builder = ContextBuilder(db_session=db, rag_pipeline=rag_pipeline)
    tool_handler = ToolHandler()
    conversation_service = ConversationService(db_session=db)
    lead_service = LeadService(db_session=db)

    return ConversationEngine(
        llm_client=None,
        context_builder=context_builder,
        tool_handler=tool_handler,
        conversation_service=conversation_service,
        lead_service=lead_service,
        db_session=db,
    )


# ---------------------------------------------------------------------------
# Update handler class
# ---------------------------------------------------------------------------


class TelegramUpdateHandler:
    """Routes a raw Telegram Update dict to the appropriate handler method.

    Stateless -- create a new instance (or reuse) for each update.
    The adapter is created internally and closed in the ``finally`` block
    of :meth:`handle_update`.
    """

    async def handle_update(
        self,
        channel: Channel,
        update: dict,
        db: AsyncSession,
    ) -> None:
        """Process a single Telegram Update.

        Args:
            channel: The Channel ORM object (must have config with bot_token).
            update: Raw Telegram Update dict.
            db: Active async database session.
        """
        config = channel.config or {}
        bot_token = config.get("bot_token", "")
        adapter = TelegramAdapter(bot_token=bot_token)

        try:
            # Handle callback queries (inline button presses)
            if "callback_query" in update:
                await self._handle_callback_query(
                    channel, update["callback_query"], adapter, db,
                )
                return

            # Handle regular messages
            message = update.get("message", {})
            text = message.get("text", "")
            chat = message.get("chat", {})
            from_user = message.get("from", {})
            external_id = str(chat.get("id", ""))

            if not external_id or not text:
                return

            user_name = from_user.get("first_name")
            if from_user.get("last_name"):
                user_name = f"{user_name} {from_user['last_name']}"

            if text.startswith("/start"):
                await self._handle_start(channel, external_id, user_name, adapter, db)
            else:
                await self._handle_text_message(channel, external_id, text, adapter, db)
        except Exception:
            logger.exception(
                "telegram_update_processing_error",
                channel_id=str(channel.id),
            )
        finally:
            await adapter.close()

    # ------------------------------------------------------------------
    # Private handler methods
    # ------------------------------------------------------------------

    async def _handle_start(
        self,
        channel: Channel,
        external_id: str,
        user_name: str | None,
        adapter: TelegramAdapter,
        db: AsyncSession,
    ) -> None:
        """Handle /start command: create lead+conversation, send greeting."""
        lead_service = LeadService(db_session=db)
        conversation_service = ConversationService(db_session=db)

        lead = await lead_service.get_or_create_lead(
            channel_id=channel.id,
            external_id=external_id,
            name=user_name,
        )

        conversation = await conversation_service.get_or_create_conversation(
            lead_id=lead.id,
            channel_id=channel.id,
        )

        messages = await conversation_service.get_messages(conversation.id, limit=1)
        if not messages:
            engine = await build_engine(db)
            _, greeting = await engine.start_conversation(
                lead_id=lead.id,
                channel_id=channel.id,
            )
        else:
            greeting = messages[0].content if messages else "Здравствуйте! Чем могу помочь?"

        await adapter.send_message(external_id, greeting)

    async def _handle_text_message(
        self,
        channel: Channel,
        external_id: str,
        text: str,
        adapter: TelegramAdapter,
        db: AsyncSession,
    ) -> None:
        """Handle a regular text message: process through AI engine, send response."""
        lead_service = LeadService(db_session=db)
        conversation_service = ConversationService(db_session=db)

        lead = await lead_service.get_or_create_lead(
            channel_id=channel.id,
            external_id=external_id,
        )

        conversation = await conversation_service.get_or_create_conversation(
            lead_id=lead.id,
            channel_id=channel.id,
        )

        # AI gate: save message but skip AI when manager handles the conversation
        if conversation.status == ConversationStatus.HANDED_OFF:
            await conversation_service.add_message(
                conversation_id=conversation.id,
                role=MessageRole.USER,
                content=text,
            )
            return

        engine = await build_engine(db)
        engine_response = await engine.process_message(
            conversation_id=conversation.id,
            user_message=text,
        )

        await adapter.send_message(external_id, engine_response.text)

        # Handle actions (booking prompt, transfer notification)
        for action in engine_response.actions:
            if action.name == "booking" and action.details.get("slots"):
                await adapter.send_booking_prompt(external_id, action.details["slots"])
            elif action.name == "transfer":
                await adapter.send_message(
                    external_id,
                    "Переключаю вас на менеджера. Ожидайте, пожалуйста.",
                )

    async def _handle_callback_query(
        self,
        channel: Channel,
        callback_query: dict,
        adapter: TelegramAdapter,
        db: AsyncSession,
    ) -> None:
        """Handle callback query (e.g., booking button press)."""
        config = channel.config or {}
        bot_token = config.get("bot_token", "")
        callback_id = callback_query.get("id", "")
        data = callback_query.get("data", "")
        from_user = callback_query.get("from", {})
        chat = callback_query.get("message", {}).get("chat", {})
        external_id = str(chat.get("id", ""))

        # Acknowledge the callback
        webhook_service = TelegramWebhookService()
        try:
            await webhook_service.answer_callback_query(bot_token, callback_id)
        finally:
            await webhook_service.close()

        if not data.startswith("book:") or not external_id:
            return

        # Parse booking data: "book:{date}:{time}"
        parts = data.split(":")
        if len(parts) >= 3:
            booking_text = f"Выбрано время: {parts[1]} {parts[2]}"
            # Process as a regular message through the engine
            await self._handle_text_message(
                channel, external_id, booking_text, adapter, db,
            )
