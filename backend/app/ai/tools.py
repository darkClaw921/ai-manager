"""Tool definitions and handlers for LLM tool_use integration.

Defines the tools available to the LLM (Anthropic format) and implements
handlers that execute the corresponding business logic.
"""

import structlog
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.qualification import QualificationStateMachine
from app.models.booking import Booking, BookingStatus
from app.models.conversation import Conversation, ConversationStatus
from app.models.lead import Lead, LeadStatus

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Tool definitions (Anthropic Messages API format)
# ---------------------------------------------------------------------------

TOOL_BOOK_APPOINTMENT = {
    "name": "book_appointment",
    "description": "Записать лида на консультацию со специалистом. Используй когда клиент согласился на встречу.",
    "input_schema": {
        "type": "object",
        "properties": {
            "date": {
                "type": "string",
                "description": "Дата консультации в формате ISO 8601 (YYYY-MM-DD)",
            },
            "time": {
                "type": "string",
                "description": "Время консультации (HH:MM)",
            },
            "notes": {
                "type": "string",
                "description": "Заметки о консультации (опционально)",
            },
        },
        "required": ["date", "time"],
    },
}

TOOL_TRANSFER_TO_MANAGER = {
    "name": "transfer_to_manager",
    "description": "Передать диалог живому менеджеру. Используй когда клиент настаивает на общении с человеком или ситуация требует участия менеджера.",
    "input_schema": {
        "type": "object",
        "properties": {
            "reason": {
                "type": "string",
                "description": "Причина передачи менеджеру",
            },
            "urgency": {
                "type": "string",
                "enum": ["low", "medium", "high"],
                "description": "Срочность обращения",
            },
        },
        "required": ["reason", "urgency"],
    },
}

TOOL_UPDATE_LEAD_INFO = {
    "name": "update_lead_info",
    "description": "Обновить информацию о лиде (клиенте). Используй когда клиент сообщает своё имя, телефон, email или компанию.",
    "input_schema": {
        "type": "object",
        "properties": {
            "field": {
                "type": "string",
                "enum": ["name", "phone", "email", "company"],
                "description": "Поле для обновления",
            },
            "value": {
                "type": "string",
                "description": "Новое значение поля",
            },
        },
        "required": ["field", "value"],
    },
}

TOOL_ADVANCE_QUALIFICATION = {
    "name": "advance_qualification",
    "description": "Продвинуть этап квалификации. Используй когда собрана ключевая информация текущего этапа (потребности, бюджет, сроки, ЛПР).",
    "input_schema": {
        "type": "object",
        "properties": {
            "collected_info": {
                "type": "string",
                "description": "Краткое описание собранной информации",
            },
            "collected_data": {
                "type": "object",
                "description": "Ключ-значение собранных данных (например {needs: 'сайт', budget: '100к'})",
            },
        },
        "required": ["collected_info"],
    },
}

# All tools list — passed to Anthropic API
TOOLS_LIST: list[dict[str, Any]] = [
    TOOL_BOOK_APPOINTMENT,
    TOOL_TRANSFER_TO_MANAGER,
    TOOL_UPDATE_LEAD_INFO,
    TOOL_ADVANCE_QUALIFICATION,
]


# ---------------------------------------------------------------------------
# Tool result dataclass
# ---------------------------------------------------------------------------

@dataclass
class ToolResult:
    """Result of a tool execution."""

    tool_use_id: str
    content: str
    is_error: bool = False
    action: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolContext:
    """Context passed to tool handlers."""

    db_session: AsyncSession
    lead_id: uuid.UUID
    conversation_id: uuid.UUID
    qualification_sm: QualificationStateMachine | None = None


# ---------------------------------------------------------------------------
# Tool handler
# ---------------------------------------------------------------------------

class ToolHandler:
    """Routes and executes tool calls from the LLM."""

    async def handle_tool_call(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        tool_use_id: str,
        context: ToolContext,
    ) -> ToolResult:
        """Route a tool call to the appropriate handler.

        Args:
            tool_name: Name of the tool to execute.
            tool_input: Input parameters from the LLM.
            tool_use_id: Unique ID of the tool_use block.
            context: Execution context with db_session, lead_id, conversation_id.

        Returns:
            ToolResult with execution outcome.
        """
        handlers = {
            "book_appointment": self._book_appointment,
            "transfer_to_manager": self._transfer_to_manager,
            "update_lead_info": self._update_lead_info,
            "advance_qualification": self._advance_qualification,
        }

        handler = handlers.get(tool_name)
        if not handler:
            logger.warning("Unknown tool called: %s", tool_name)
            return ToolResult(
                tool_use_id=tool_use_id,
                content=f"Неизвестный инструмент: {tool_name}",
                is_error=True,
            )

        try:
            result = await handler(tool_input, tool_use_id, context)
            logger.info("Tool %s executed successfully for lead %s", tool_name, context.lead_id)
            return result
        except Exception as e:
            logger.error("Tool %s failed: %s", tool_name, e)
            return ToolResult(
                tool_use_id=tool_use_id,
                content=f"Ошибка при выполнении {tool_name}: {e!s}",
                is_error=True,
            )

    async def _book_appointment(
        self,
        tool_input: dict[str, Any],
        tool_use_id: str,
        context: ToolContext,
    ) -> ToolResult:
        """Create a booking in the database."""
        date_str = tool_input["date"]
        time_str = tool_input["time"]
        notes = tool_input.get("notes", "")

        # Parse date and time
        scheduled_at = datetime.fromisoformat(f"{date_str}T{time_str}:00")

        booking = Booking(
            lead_id=context.lead_id,
            scheduled_at=scheduled_at,
            notes=notes,
            status=BookingStatus.PENDING,
        )
        context.db_session.add(booking)

        # Update lead status
        result = await context.db_session.execute(
            select(Lead).where(Lead.id == context.lead_id)
        )
        lead = result.scalar_one_or_none()
        if lead:
            lead.status = LeadStatus.BOOKED

        await context.db_session.flush()

        return ToolResult(
            tool_use_id=tool_use_id,
            content=f"Консультация успешно записана на {date_str} в {time_str}.",
            action="book_appointment",
            details={
                "booking_id": str(booking.id),
                "scheduled_at": scheduled_at.isoformat(),
                "notes": notes,
            },
        )

    async def _transfer_to_manager(
        self,
        tool_input: dict[str, Any],
        tool_use_id: str,
        context: ToolContext,
    ) -> ToolResult:
        """Transfer conversation to a live manager."""
        reason = tool_input["reason"]
        urgency = tool_input["urgency"]

        # Update conversation status
        result = await context.db_session.execute(
            select(Conversation).where(Conversation.id == context.conversation_id)
        )
        conversation = result.scalar_one_or_none()
        if conversation:
            conversation.status = ConversationStatus.HANDED_OFF

        # Update lead status
        result = await context.db_session.execute(
            select(Lead).where(Lead.id == context.lead_id)
        )
        lead = result.scalar_one_or_none()
        if lead:
            lead.status = LeadStatus.HANDED_OFF

        await context.db_session.flush()

        return ToolResult(
            tool_use_id=tool_use_id,
            content=f"Диалог передан менеджеру. Причина: {reason}. Срочность: {urgency}.",
            action="transfer_to_manager",
            details={
                "reason": reason,
                "urgency": urgency,
            },
        )

    async def _update_lead_info(
        self,
        tool_input: dict[str, Any],
        tool_use_id: str,
        context: ToolContext,
    ) -> ToolResult:
        """Update a specific field on the lead."""
        field_name = tool_input["field"]
        value = tool_input["value"]

        allowed_fields = {"name", "phone", "email", "company"}
        if field_name not in allowed_fields:
            return ToolResult(
                tool_use_id=tool_use_id,
                content=f"Недопустимое поле: {field_name}",
                is_error=True,
            )

        result = await context.db_session.execute(
            select(Lead).where(Lead.id == context.lead_id)
        )
        lead = result.scalar_one_or_none()
        if not lead:
            return ToolResult(
                tool_use_id=tool_use_id,
                content="Лид не найден",
                is_error=True,
            )

        setattr(lead, field_name, value)
        await context.db_session.flush()

        return ToolResult(
            tool_use_id=tool_use_id,
            content=f"Информация о клиенте обновлена: {field_name} = {value}",
            action="update_lead_info",
            details={"field": field_name, "value": value},
        )

    async def _advance_qualification(
        self,
        tool_input: dict[str, Any],
        tool_use_id: str,
        context: ToolContext,
    ) -> ToolResult:
        """Advance the qualification stage using the state machine."""
        if not context.qualification_sm:
            return ToolResult(
                tool_use_id=tool_use_id,
                content="Ошибка: не удалось загрузить квалификацию",
                is_error=True,
            )

        collected_data = tool_input.get("collected_data", {})
        collected_info = tool_input.get("collected_info", "")
        if collected_info:
            collected_data["_info"] = collected_info

        try:
            # Capture current stage and score BEFORE advancing
            current_stage_value = context.qualification_sm.current_stage.value
            score_before = context.qualification_sm.calculate_interest_score()

            new_stage = context.qualification_sm.advance(collected_data)
            score = context.qualification_sm.calculate_interest_score()

            # Store score history entry
            score_delta = score - score_before
            history = context.qualification_sm._qualification_data.setdefault("_score_history", [])
            history.append({
                "stage": current_stage_value,
                "score_added": score_delta,
                "total_score": score,
                "info": collected_info,
            })

            return ToolResult(
                tool_use_id=tool_use_id,
                content=f"Этап квалификации продвинут до {new_stage.value}. Балл: {score}/100",
                action="advance_qualification",
                details={"stage": new_stage.value, "score": score},
            )
        except Exception as e:
            return ToolResult(
                tool_use_id=tool_use_id,
                content=f"Ошибка: {e}",
                is_error=True,
            )
