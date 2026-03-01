"""Format converters between Anthropic (internal) and OpenAI wire formats.

The system uses Anthropic-style message format internally (in engine.py).
These functions convert at the client boundary when using OpenAI-compatible providers.
"""

import json
from typing import Any

import structlog

from app.ai.base_client import MessageResponse

logger = structlog.get_logger(__name__)


def anthropic_tools_to_openai(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert Anthropic tool definitions to OpenAI function format.

    Anthropic: {"name": "...", "description": "...", "input_schema": {...}}
    OpenAI:    {"type": "function", "function": {"name": "...", "description": "...", "parameters": {...}}}
    """
    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": tool.get("input_schema", {}),
            },
        }
        for tool in tools
    ]


def anthropic_messages_to_openai(
    messages: list[dict[str, Any]],
    system: str | None = None,
) -> list[dict[str, Any]]:
    """Convert Anthropic message format to OpenAI format.

    Handles:
    - System prompt: separate param -> {"role": "system"} message
    - Tool result blocks in user content -> {"role": "tool"} messages
    - Assistant tool_use blocks in content list -> tool_calls field
    - is_error flag: prepends "[ERROR] " to content (OpenAI has no native is_error)
    """
    openai_messages: list[dict[str, Any]] = []

    if system:
        openai_messages.append({"role": "system", "content": system})

    for msg in messages:
        role = msg["role"]
        content = msg["content"]

        # Case 1: Simple text message (string content)
        if isinstance(content, str):
            openai_messages.append({"role": role, "content": content})
            continue

        # Case 2: List content (tool_use or tool_result blocks)
        if isinstance(content, list):
            # Check for tool_result blocks (from user role, Anthropic format)
            tool_results = [b for b in content if b.get("type") == "tool_result"]
            if tool_results:
                for tr in tool_results:
                    result_content = tr.get("content", "")
                    if tr.get("is_error"):
                        result_content = f"[ERROR] {result_content}"
                    openai_messages.append({
                        "role": "tool",
                        "tool_call_id": tr["tool_use_id"],
                        "content": str(result_content),
                    })
                continue

            # Check for tool_use blocks (from assistant role)
            tool_uses = [b for b in content if b.get("type") == "tool_use"]
            text_blocks = [b for b in content if b.get("type") == "text"]

            if tool_uses:
                text_content = "\n".join(b["text"] for b in text_blocks) if text_blocks else None
                openai_messages.append({
                    "role": "assistant",
                    "content": text_content,
                    "tool_calls": [
                        {
                            "id": tu["id"],
                            "type": "function",
                            "function": {
                                "name": tu["name"],
                                "arguments": json.dumps(tu["input"]),
                            },
                        }
                        for tu in tool_uses
                    ],
                })
                continue

            # Fallback: join text blocks
            combined_text = "\n".join(
                b.get("text", "") for b in content if b.get("type") == "text"
            )
            if combined_text:
                openai_messages.append({"role": role, "content": combined_text})

    return openai_messages


def openai_response_to_message_response(
    choice: Any,
    model: str,
    usage: dict[str, int],
) -> MessageResponse:
    """Convert OpenAI response choice to normalized MessageResponse.

    Maps:
    - finish_reason "tool_calls" -> stop_reason "tool_use"
    - finish_reason "stop" -> stop_reason "end_turn"
    - tool_calls -> content blocks {"type": "tool_use", ...}
    """
    message = choice.message
    content: list[dict[str, Any]] = []

    logger.debug(
        "openai_response_raw",
        finish_reason=choice.finish_reason,
        has_content=message.content is not None,
        content_length=len(message.content) if message.content else 0,
        content_preview=message.content[:200] if message.content else "<None>",
        has_tool_calls=message.tool_calls is not None,
        reasoning_content=getattr(message, "reasoning_content", "<no attr>"),
    )

    # Try to get text from content or reasoning_content (for reasoning models)
    text_content = message.content
    if not text_content and hasattr(message, "reasoning_content") and message.reasoning_content:
        logger.info("openai_using_reasoning_content_fallback")
        text_content = message.reasoning_content

    if text_content:
        content.append({"type": "text", "text": text_content})

    if message.tool_calls:
        for tc in message.tool_calls:
            try:
                tool_input = json.loads(tc.function.arguments)
            except (json.JSONDecodeError, TypeError):
                tool_input = {}

            content.append({
                "type": "tool_use",
                "id": tc.id,
                "name": tc.function.name,
                "input": tool_input,
            })

    # Normalize stop reason
    stop_reason = "end_turn"
    if choice.finish_reason == "tool_calls":
        stop_reason = "tool_use"

    return MessageResponse(
        content=content,
        stop_reason=stop_reason,
        model=model,
        usage=usage,
    )
