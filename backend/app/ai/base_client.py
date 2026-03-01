"""Abstract base class for LLM clients and shared response model."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MessageResponse:
    """Structured response from LLM — provider-agnostic.

    Content blocks use normalized Anthropic-style format:
      - Text: {"type": "text", "text": "..."}
      - Tool use: {"type": "tool_use", "id": "...", "name": "...", "input": {...}}
    """

    content: list[dict[str, Any]]
    stop_reason: str | None = None
    model: str = ""
    usage: dict[str, int] = field(default_factory=dict)

    @property
    def text(self) -> str:
        """Extract text content from response."""
        texts = [block["text"] for block in self.content if block.get("type") == "text"]
        return "\n".join(texts)

    @property
    def tool_calls(self) -> list[dict[str, Any]]:
        """Extract tool_use blocks from response."""
        return [block for block in self.content if block.get("type") == "tool_use"]

    @property
    def has_tool_use(self) -> bool:
        """Check if response contains tool use requests."""
        return self.stop_reason == "tool_use"


class BaseLLMClient(ABC):
    """Abstract LLM client interface. All providers must implement this."""

    @abstractmethod
    async def send_message(
        self,
        messages: list[dict[str, Any]],
        system: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: dict[str, Any] | None = None,
        max_tokens: int | None = None,
        model: str | None = None,
    ) -> MessageResponse:
        """Send a message to the LLM and return a structured response."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Close the underlying HTTP client."""
        ...
