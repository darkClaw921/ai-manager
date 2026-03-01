"""Anthropic LLM client wrapper with retry logic and error handling."""

import time
from typing import Any

import anthropic
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.ai.base_client import BaseLLMClient, MessageResponse  # noqa: F401 -- re-export

logger = structlog.get_logger(__name__)


class AnthropicClient(BaseLLMClient):
    """Wrapper around Anthropic AsyncAnthropic client with retry and error handling.

    API key is always provided by client_factory from DB settings.
    """

    def __init__(
        self,
        api_key: str = "",
        model: str = "claude-sonnet-4-5-20250929",
        max_tokens: int = 4096,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._max_tokens = max_tokens
        self._client = anthropic.AsyncAnthropic(
            api_key=self._api_key,
            max_retries=0,  # We handle retries ourselves via tenacity
        )

    @retry(
        retry=retry_if_exception_type(
            (anthropic.RateLimitError, anthropic.InternalServerError, anthropic.APIConnectionError)
        ),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        before_sleep=lambda retry_state: logger.warning(
            "LLM request retry %d/%d after error: %s",
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
        """Send a message to the Anthropic API and return a structured response.

        Args:
            messages: Conversation messages in Anthropic format [{role, content}].
            system: System prompt.
            tools: Tool definitions for tool_use.
            tool_choice: Tool choice configuration.
            max_tokens: Override default max_tokens.
            model: Override default model.

        Returns:
            MessageResponse with content, stop_reason, model, and usage.

        Raises:
            anthropic.AuthenticationError: If API key is invalid.
            anthropic.BadRequestError: If request is malformed.
            anthropic.RateLimitError: After exhausting retries on rate limit.
            anthropic.APIConnectionError: After exhausting retries on connection errors.
        """
        kwargs: dict[str, Any] = {
            "model": model or self._model,
            "max_tokens": max_tokens or self._max_tokens,
            "messages": messages,
        }

        if system:
            kwargs["system"] = system

        if tools:
            kwargs["tools"] = tools

        if tool_choice:
            kwargs["tool_choice"] = tool_choice

        logger.debug(
            "llm_request_started",
            model=kwargs["model"],
            messages_count=len(messages),
            tools_count=len(tools) if tools else 0,
        )

        start_time = time.perf_counter()

        try:
            response = await self._client.messages.create(**kwargs)
        except anthropic.AuthenticationError:
            logger.error("llm_auth_failed", error="check API key in admin panel settings")
            raise
        except anthropic.BadRequestError as e:
            logger.error("llm_bad_request", error=e.message)
            raise

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # Convert response to our dataclass
        content = []
        for block in response.content:
            if block.type == "text":
                content.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                content.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })

        result = MessageResponse(
            content=content,
            stop_reason=response.stop_reason,
            model=response.model,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
        )

        logger.info(
            "llm_request_completed",
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


# Backward compatibility alias
LLMClient = AnthropicClient
