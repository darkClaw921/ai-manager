"""OpenRouter LLM client — uses OpenAI SDK with custom base_url.

OpenRouter is fully OpenAI-compatible, so we extend OpenAIClient
and only override __init__ to set the base URL and optional headers.
"""

from app.ai.openai_client import OpenAIClient


class OpenRouterClient(OpenAIClient):
    """OpenRouter client. Inherits from OpenAIClient, overrides only __init__."""

    OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(
        self,
        api_key: str,
        model: str = "anthropic/claude-sonnet-4",
        max_tokens: int = 4096,
        site_url: str = "",
        site_name: str = "AI Lead Manager",
    ) -> None:
        extra_headers: dict[str, str] = {}
        if site_url:
            extra_headers["HTTP-Referer"] = site_url
        if site_name:
            extra_headers["X-Title"] = site_name

        super().__init__(
            api_key=api_key,
            model=model,
            max_tokens=max_tokens,
            base_url=self.OPENROUTER_BASE_URL,
            default_headers=extra_headers,
        )
