"""ConversationEngine -- the main orchestrator for AI-powered conversations.

Implements the full message processing pipeline:
  1. Save user message to DB
  2. Build LLM context (history, RAG, qualification state)
  3. Call LLM
  4. Handle tool_use loop (max 5 iterations)
  5. Update qualification data
  6. Save assistant response to DB
  7. Return structured response
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base_client import BaseLLMClient
from app.ai.client_factory import create_llm_client
from app.ai.context_builder import ContextBuilder
from app.ai.llm_client import LLMClient
from app.ai.prompts import build_greeting
from app.ai.qualification import QualificationStage
from app.ai.tools import ToolContext, ToolHandler, ToolResult
from app.models.conversation import ConversationStatus, MessageRole
from app.services.conversation_service import ConversationService
from app.services.lead_service import LeadService

logger = structlog.get_logger(__name__)

# Maximum tool_use loop iterations (guard against infinite loops)
MAX_TOOL_ITERATIONS = 5


@dataclass
class Action:
    """An action executed during message processing."""

    name: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class EngineResponse:
    """Structured response from the conversation engine."""

    text: str
    actions: list[Action] = field(default_factory=list)
    qualification_stage: QualificationStage = QualificationStage.INITIAL
    interest_score: int = 0


class ConversationEngine:
    """Main orchestrator for AI-powered lead qualification conversations.

    Coordinates between the LLM client, context builder, tool handler,
    and database services to process user messages and generate responses.

    Supports per-owner LLM client creation: when db_session is provided,
    the engine creates an owner-specific LLM client using owner_id from
    the conversation's channel. Falls back to the pre-built llm_client
    if db_session is not available.
    """

    def __init__(
        self,
        llm_client: LLMClient | BaseLLMClient | None,
        context_builder: ContextBuilder,
        tool_handler: ToolHandler,
        conversation_service: ConversationService,
        lead_service: LeadService,
        db_session: AsyncSession | None = None,
    ) -> None:
        self._llm = llm_client
        self._context = context_builder
        self._tools = tool_handler
        self._conversations = conversation_service
        self._leads = lead_service
        self._db = db_session

    async def _get_llm_client(
        self, owner_id: uuid.UUID | None = None,
    ) -> LLMClient | BaseLLMClient:
        """Get or create the LLM client, using per-owner settings if available.

        When db_session is available, creates a new LLM client with the
        owner's API key. Otherwise, uses the pre-built client.
        """
        if self._db is not None:
            return await create_llm_client(self._db, owner_id=owner_id)
        if self._llm is not None:
            return self._llm
        raise RuntimeError("No LLM client or db_session available")

    async def process_message(
        self,
        conversation_id: uuid.UUID,
        user_message: str,
    ) -> EngineResponse:
        """Process a user message and return an AI response.

        Full pipeline:
            1. Save user message to DB
            2. Build LLM context (determines owner_id from channel)
            3. Create per-owner LLM client
            4. Call LLM with tool_use loop
            5. Update qualification data
            6. Save assistant response
            7. Return EngineResponse

        Args:
            conversation_id: UUID of the active conversation.
            user_message: The user's message text.

        Returns:
            EngineResponse with AI text, executed actions, and qualification state.
        """
        # 1. Save user message
        await self._conversations.add_message(
            conversation_id=conversation_id,
            role=MessageRole.USER,
            content=user_message,
        )

        # 2. Build context (determines owner_id from channel)
        ctx = await self._context.build_context(conversation_id, user_message)

        # 3. Get per-owner LLM client
        llm_client = await self._get_llm_client(owner_id=ctx.owner_id)

        # Add the new user message to the API messages list
        api_messages = ctx.messages + [{"role": "user", "content": user_message}]

        # 4. Call LLM with tool_use loop
        actions: list[Action] = []
        response_text = ""

        for iteration in range(MAX_TOOL_ITERATIONS):
            llm_response = await llm_client.send_message(
                messages=api_messages,
                system=ctx.system_prompt,
                tools=ctx.tools,
            )

            if llm_response.has_tool_use:
                # Process tool calls
                tool_results = []
                for tool_call in llm_response.tool_calls:
                    tool_context = ToolContext(
                        db_session=self._conversations._db,
                        lead_id=ctx.lead.id,
                        conversation_id=conversation_id,
                        qualification_sm=ctx.qualification_sm,
                    )
                    result = await self._tools.handle_tool_call(
                        tool_name=tool_call["name"],
                        tool_input=tool_call["input"],
                        tool_use_id=tool_call["id"],
                        context=tool_context,
                    )
                    tool_results.append(result)

                    if not result.is_error and result.action:
                        actions.append(Action(
                            name=result.action,
                            details=result.details,
                        ))

                # Append assistant message (with tool_use blocks) and tool results
                api_messages.append({"role": "assistant", "content": llm_response.content})
                api_messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": r.tool_use_id,
                            "content": r.content,
                            "is_error": r.is_error,
                        }
                        for r in tool_results
                    ],
                })

                logger.debug(
                    "tool_use_iteration",
                    iteration=iteration + 1,
                    tool_calls_count=len(tool_results),
                    conversation_id=str(conversation_id),
                )
            else:
                # Text response -- done
                response_text = llm_response.text
                break
        else:
            # Max iterations reached without a text response
            logger.warning(
                "max_tool_iterations_reached",
                max_iterations=MAX_TOOL_ITERATIONS,
                conversation_id=str(conversation_id),
            )
            # Extract any text from the last response
            response_text = llm_response.text or "Извините, произошла ошибка. Попробуйте ещё раз."

        # 5. Update qualification data
        qualification_sm = ctx.qualification_sm
        interest_score = qualification_sm.calculate_interest_score()

        await self._leads.update_qualification(
            lead_id=ctx.lead.id,
            stage=qualification_sm.current_stage.value,
            data=qualification_sm.get_qualification_data(),
            score=interest_score,
        )

        # 6. Save assistant response
        await self._conversations.add_message(
            conversation_id=conversation_id,
            role=MessageRole.ASSISTANT,
            content=response_text,
        )

        # 7. Return response
        return EngineResponse(
            text=response_text,
            actions=actions,
            qualification_stage=qualification_sm.current_stage,
            interest_score=interest_score,
        )

    async def start_conversation(
        self,
        lead_id: uuid.UUID,
        channel_id: uuid.UUID,
    ) -> tuple[uuid.UUID, str]:
        """Start a new conversation with a greeting message.

        Creates a conversation record and sends the initial greeting.

        Args:
            lead_id: UUID of the lead.
            channel_id: UUID of the channel.

        Returns:
            Tuple of (conversation_id, greeting_text).
        """
        # Get or create conversation
        conversation = await self._conversations.get_or_create_conversation(
            lead_id=lead_id,
            channel_id=channel_id,
        )

        # Get lead name for personalized greeting
        lead = await self._leads.get_lead(lead_id)
        lead_name = lead.name if lead else None

        greeting = build_greeting(lead_name)

        # Save greeting as assistant message
        await self._conversations.add_message(
            conversation_id=conversation.id,
            role=MessageRole.ASSISTANT,
            content=greeting,
        )

        # Move lead to qualifying if still new
        if lead and lead.qualification_stage in (None, "initial"):
            await self._leads.update_qualification(
                lead_id=lead_id,
                stage=QualificationStage.NEEDS_DISCOVERY.value,
                data={"initial": True},
                score=0,
            )

        logger.info(
            "conversation_started",
            conversation_id=str(conversation.id),
            lead_id=str(lead_id),
            channel_id=str(channel_id),
        )

        return conversation.id, greeting
