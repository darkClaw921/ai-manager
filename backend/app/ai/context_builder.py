"""Context builder: assembles the full LLM context from DB, RAG, and qualification state.

Combines conversation history, RAG results, qualification stage instructions,
and lead info into a structured LLMContext ready for the Anthropic API call.
"""

import datetime
import structlog
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.prompts import (
    SYSTEM_PROMPT,
    build_lead_info,
    build_rag_context,
    build_stage_instructions,
)
from app.ai.qualification import QualificationStage, QualificationStateMachine
from app.ai.rag import RAGPipeline
from app.ai.tools import TOOLS_LIST
from app.models.channel import Channel
from app.models.conversation import Conversation, Message, MessageRole
from app.models.lead import Lead
from app.models.script import QualificationScript
from app.models.settings import SystemSettings

logger = structlog.get_logger(__name__)

# Default number of recent messages to include in context
DEFAULT_HISTORY_LIMIT = 20

# Russian month names (genitive case) and weekday names
MONTHS_RU = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля",
    5: "мая", 6: "июня", 7: "июля", 8: "августа",
    9: "сентября", 10: "октября", 11: "ноября", 12: "декабря",
}

WEEKDAYS_RU = {
    0: "понедельник", 1: "вторник", 2: "среда", 3: "четверг",
    4: "пятница", 5: "суббота", 6: "воскресенье",
}


def format_datetime_ru() -> str:
    """Return current date and time as a human-readable Russian string.

    Example: '26 февраля 2026, четверг, 14:30'
    """
    now = datetime.datetime.now()
    return (
        f"{now.day} {MONTHS_RU[now.month]} {now.year}, "
        f"{WEEKDAYS_RU[now.weekday()]}, {now.hour:02d}:{now.minute:02d}"
    )


@dataclass
class LLMContext:
    """Structured context ready for an LLM API call."""

    system_prompt: str
    messages: list[dict[str, Any]]
    tools: list[dict[str, Any]]
    lead: Lead
    conversation: Conversation
    qualification_stage: QualificationStage
    qualification_sm: QualificationStateMachine = field(repr=False)
    owner_id: uuid.UUID | None = None


class ContextBuilder:
    """Builds the full LLM context for a conversation turn.

    Loads conversation history from DB, retrieves RAG context from Qdrant,
    determines the qualification stage, and assembles the system prompt.
    """

    def __init__(
        self,
        db_session: AsyncSession,
        rag_pipeline: RAGPipeline,
    ) -> None:
        self._db = db_session
        self._rag = rag_pipeline

    async def build_context(
        self,
        conversation_id: uuid.UUID,
        new_message: str,
    ) -> LLMContext:
        """Build the complete LLM context for a conversation turn.

        Steps:
            1. Load conversation, lead, and channel (for owner_id) from DB
            2. Load recent message history (per-owner setting)
            3. Load qualification script for the channel
            4. Get RAG context (filtered by owner_id and script_id)
            5. Build qualification state machine (with score_config)
            6. Assemble system prompt
            7. Format messages for Anthropic API

        Args:
            conversation_id: UUID of the active conversation.
            new_message: The new user message text.

        Returns:
            LLMContext with all data needed for the LLM call.
        """
        # 1. Load conversation with lead
        conversation = await self._load_conversation(conversation_id)
        lead = await self._load_lead(conversation.lead_id)

        # Determine owner_id from channel
        owner_id = await self._get_channel_owner_id(conversation.channel_id)

        # 2. Load message history (per-owner setting)
        history_limit = await self._get_history_limit(owner_id=owner_id)
        messages = await self._load_messages(conversation_id, limit=history_limit)

        # 3. Load script for channel (needed before RAG for script_id filter)
        script = await self._load_script_for_channel(conversation.channel_id)

        # 4. Get RAG context (filtered by owner_id and script_id)
        rag_context = await self._rag.get_relevant_context(
            new_message, owner_id=owner_id,
            script_id=script.id if script else None,
        )

        # 5. Build qualification state machine
        qualification_sm = QualificationStateMachine(
            current_stage=lead.qualification_stage,
            qualification_data=lead.qualification_data or {},
            script_stages=script.stages if script else [],
            score_config=script.score_config if script else None,
        )

        # 6. Build system prompt
        lead_info = build_lead_info(
            lead_name=lead.name,
            lead_status=lead.status.value if lead.status else "new",
            qualification_stage=qualification_sm.current_stage.value,
            qualification_data=lead.qualification_data,
            interest_score=lead.interest_score,
        )

        stage_instructions = build_stage_instructions(
            stage=qualification_sm.current_stage.value,
            expected_info=qualification_sm.get_expected_info(),
            script_prompt=qualification_sm.get_current_prompt(),
        )

        rag_section = ""
        if rag_context.has_context:
            faq_items = [
                {"question": item.question, "answer": item.answer}
                for item in rag_context.faq_items
            ]
            objections = [
                {"pattern": obj.pattern, "response": obj.response}
                for obj in rag_context.objections
            ]
            rag_section = build_rag_context(faq_items=faq_items, objections=objections)

        system_prompt = SYSTEM_PROMPT.format(
            current_datetime=format_datetime_ru(),
            lead_info=lead_info,
            stage_instructions=stage_instructions,
            rag_context=rag_section,
        )

        # 6b. Add hint if conversation has manager messages
        has_manager_messages = any(
            msg.role == MessageRole.ASSISTANT and (msg.metadata_ or {}).get("sender") == "manager"
            for msg in messages
        )
        if has_manager_messages:
            system_prompt += (
                "\n\nВажно: некоторые предыдущие ответы в этом диалоге были написаны "
                "менеджером-человеком. Продолжай диалог естественно, без специального приветствия."
            )

        # 7. Format messages for Anthropic API
        api_messages = self._format_messages(messages)

        return LLMContext(
            system_prompt=system_prompt,
            messages=api_messages,
            tools=TOOLS_LIST,
            lead=lead,
            conversation=conversation,
            qualification_stage=qualification_sm.current_stage,
            qualification_sm=qualification_sm,
            owner_id=owner_id,
        )

    async def _load_conversation(self, conversation_id: uuid.UUID) -> Conversation:
        """Load a conversation from the database."""
        result = await self._db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conversation = result.scalar_one_or_none()
        if not conversation:
            raise ValueError(f"Conversation not found: {conversation_id}")
        return conversation

    async def _load_lead(self, lead_id: uuid.UUID) -> Lead:
        """Load a lead from the database."""
        result = await self._db.execute(
            select(Lead).where(Lead.id == lead_id)
        )
        lead = result.scalar_one_or_none()
        if not lead:
            raise ValueError(f"Lead not found: {lead_id}")
        return lead

    async def _load_messages(
        self,
        conversation_id: uuid.UUID,
        limit: int = DEFAULT_HISTORY_LIMIT,
    ) -> list[Message]:
        """Load recent messages for a conversation, ordered chronologically."""
        result = await self._db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        messages = list(result.scalars().all())
        messages.reverse()  # Chronological order
        return messages

    async def _load_script_for_channel(
        self, channel_id: uuid.UUID,
    ) -> QualificationScript | None:
        """Load the qualification script assigned to a channel.

        If the channel has a qualification_script_id set, loads that specific
        script. Otherwise falls back to the global active script via
        _load_active_script().
        """
        try:
            result = await self._db.execute(
                select(Channel).where(Channel.id == channel_id)
            )
            channel = result.scalar_one_or_none()

            if channel and channel.qualification_script_id is not None:
                script_result = await self._db.execute(
                    select(QualificationScript).where(
                        QualificationScript.id == channel.qualification_script_id
                    )
                )
                script = script_result.scalar_one_or_none()
                if script is not None:
                    logger.info(
                        "loaded_script_for_channel",
                        channel_id=str(channel_id),
                        script_id=str(script.id),
                    )
                    return script
                logger.warning(
                    "channel_script_not_found_fallback",
                    channel_id=str(channel_id),
                    script_id=str(channel.qualification_script_id),
                )
        except Exception:
            logger.exception(
                "error_loading_channel_script",
                channel_id=str(channel_id),
            )

        # Fallback to global active script
        logger.info("using_global_active_script", channel_id=str(channel_id))
        return await self._load_active_script()

    async def _load_active_script(self) -> QualificationScript | None:
        """Load the most recently created active qualification script."""
        result = await self._db.execute(
            select(QualificationScript)
            .where(QualificationScript.is_active.is_(True))
            .order_by(QualificationScript.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _get_channel_owner_id(
        self, channel_id: uuid.UUID,
    ) -> uuid.UUID | None:
        """Get the owner_id for a channel.

        Returns None if channel not found or has no owner.
        """
        try:
            result = await self._db.execute(
                select(Channel.owner_id).where(Channel.id == channel_id)
            )
            return result.scalar_one_or_none()
        except Exception:
            logger.exception("error_loading_channel_owner", channel_id=str(channel_id))
            return None

    async def _get_history_limit(
        self, owner_id: uuid.UUID | None = None,
    ) -> int:
        """Get the message history limit from system settings, or use default.

        Checks per-owner setting first, then falls back to global setting.
        """
        try:
            # Try per-owner setting first
            if owner_id is not None:
                result = await self._db.execute(
                    select(SystemSettings).where(
                        SystemSettings.key == "conversation_history_limit",
                        SystemSettings.owner_id == owner_id,
                    )
                )
                setting = result.scalar_one_or_none()
                if setting and setting.value:
                    return int(setting.value.get("value", DEFAULT_HISTORY_LIMIT))

            # Fall back to global setting
            result = await self._db.execute(
                select(SystemSettings).where(
                    SystemSettings.key == "conversation_history_limit",
                    SystemSettings.owner_id.is_(None),
                )
            )
            setting = result.scalar_one_or_none()
            if setting and setting.value:
                return int(setting.value.get("value", DEFAULT_HISTORY_LIMIT))
        except Exception:
            pass
        return DEFAULT_HISTORY_LIMIT

    @staticmethod
    def _format_messages(messages: list[Message]) -> list[dict[str, Any]]:
        """Format DB messages into Anthropic API message format.

        Only includes user and assistant messages (skips system).
        """
        api_messages: list[dict[str, Any]] = []
        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                continue
            api_messages.append({
                "role": msg.role.value,
                "content": msg.content,
            })
        return api_messages
