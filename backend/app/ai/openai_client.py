"""OpenAI LLM client with retry logic and format conversion."""

import time
from typing import Any

import structlog
from openai import (
    APIConnectionError,
    AsyncOpenAI,
    InternalServerError,
    RateLimitError,
)
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.ai.base_client import BaseLLMClient, MessageResponse
from app.ai.format_converter import (
    anthropic_messages_to_openai,
    anthropic_tools_to_openai,
    openai_response_to_message_response,
)

logger = structlog.get_logger(__name__)


class OpenAIClient(BaseLLMClient):
    """OpenAI LLM client. Converts Anthropic-style messages/tools to OpenAI format."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o",
        max_tokens: int = 4096,
        base_url: str | None = None,
        default_headers: dict[str, str] | None = None,
    ) -> None:
        self._model = model
        self._max_tokens = max_tokens
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            max_retries=0,
            default_headers=default_headers or {},
        )

    @retry(
        retry=retry_if_exception_type(
            (RateLimitError, InternalServerError, APIConnectionError)
        ),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        before_sleep=lambda retry_state: logger.warning(
            "OpenAI request retry %d/%d after error: %s",
            retry_state.attempt_number,
            3,
            retry_state.outcome.exception() if retry_state.outcome else "unknown",
        ),
    )
    async def send_message(
        self,
        messages: list[dict[str, Any]],
        system: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: dict[str, Any] | None = None,
        max_tokens: int | None = None,
        model: str | None = None,
    ) -> MessageResponse:
        """Send a message to OpenAI API.

        Converts Anthropic-style messages and tools to OpenAI format,
        sends the request, and normalizes the response back to MessageResponse.
        """
        # Convert message format
        openai_messages = anthropic_messages_to_openai(messages, system)

        kwargs: dict[str, Any] = {
            "model": model or self._model,
            "max_tokens": max_tokens or self._max_tokens,
            "messages": openai_messages,
        }

        if tools:
            kwargs["tools"] = anthropic_tools_to_openai(tools)

        logger.debug(
            "openai_request_started",
            model=kwargs["model"],
            messages_count=len(openai_messages),
            tools_count=len(tools) if tools else 0,
        )

        start_time = time.perf_counter()
        response = await self._client.chat.completions.create(**kwargs)
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        usage = {
            "input_tokens": response.usage.prompt_tokens if response.usage else 0,
            "output_tokens": response.usage.completion_tokens if response.usage else 0,
        }

        result = openai_response_to_message_response(
            choice=response.choices[0],
            model=response.model,
            usage=usage,
        )

        logger.info(
            "llm_request_completed",
            provider="openai",
            model=result.model,
            stop_reason=result.stop_reason,
            input_tokens=result.usage.get("input_tokens"),
            output_tokens=result.usage.get("output_tokens"),
            duration_ms=duration_ms,
        )

        return result

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.close()
