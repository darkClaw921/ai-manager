"""Factory for creating LLM clients based on system settings.

All LLM API keys are stored in DB (system_settings table) and managed
by users via the admin panel. No env variables are used for API keys.

Key lookup: per-manager DB (owner_id = UUID) → global DB (owner_id IS NULL).
"""

import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base_client import BaseLLMClient
from app.models.settings import SystemSettings

logger = structlog.get_logger(__name__)


async def get_setting_value(
    db: AsyncSession,
    key: str,
    default: str = "",
    owner_id: uuid.UUID | None = None,
) -> str:
    """Read a single setting value from the system_settings table.

    When owner_id is provided, looks up the per-owner setting first.
    Falls back to the global setting (owner_id IS NULL) if per-owner
    setting is not found.
    """
    value = None

    # Try per-owner setting first
    if owner_id is not None:
        result = await db.execute(
            select(SystemSettings.value).where(
                SystemSettings.key == key,
                SystemSettings.owner_id == owner_id,
            )
        )
        value = result.scalar_one_or_none()

    # Fall back to global setting
    if value is None:
        result = await db.execute(
            select(SystemSettings.value).where(
                SystemSettings.key == key,
                SystemSettings.owner_id.is_(None),
            )
        )
        value = result.scalar_one_or_none()

    if value is None:
        return default

    # JSONB value can be a raw string, number, or dict
    if isinstance(value, dict):
        return str(value.get("value", default))
    return str(value)


async def create_llm_client(
    db: AsyncSession,
    owner_id: uuid.UUID | None = None,
) -> BaseLLMClient:
    """Create the appropriate LLM client based on DB settings.

    All configuration is read from DB (system_settings table):
      - llm_provider: "anthropic" | "openai" | "openrouter"
      - ai_model: model name string
      - *_api_key: provider API keys (set by users via admin panel)

    When owner_id is provided, uses per-manager settings with fallback
    to global settings. This allows each manager to use their own API key.

    Args:
        db: Async SQLAlchemy session.
        owner_id: Optional manager UUID for per-manager settings.

    Returns:
        Configured LLM client instance.
    """
    provider = await get_setting_value(db, "llm_provider", "anthropic", owner_id=owner_id)
    model = await get_setting_value(db, "ai_model", "", owner_id=owner_id)

    if provider == "openai":
        from app.ai.openai_client import OpenAIClient

        api_key = await get_setting_value(db, "openai_api_key", "", owner_id=owner_id)
        logger.debug("creating_llm_client", provider="openai", model=model or "gpt-4o", owner_id=str(owner_id))
        return OpenAIClient(
            api_key=api_key,
            model=model or "gpt-4o",
        )

    if provider == "openrouter":
        from app.ai.openrouter_client import OpenRouterClient

        api_key = await get_setting_value(db, "openrouter_api_key", "", owner_id=owner_id)
        logger.debug("creating_llm_client", provider="openrouter", model=model or "anthropic/claude-sonnet-4", owner_id=str(owner_id))
        return OpenRouterClient(
            api_key=api_key,
            model=model or "anthropic/claude-sonnet-4",
        )

    # Default: Anthropic
    from app.ai.llm_client import AnthropicClient

    api_key = await get_setting_value(db, "anthropic_api_key", "", owner_id=owner_id)
    logger.debug("creating_llm_client", provider="anthropic", model=model or "claude-sonnet-4-5-20250929", owner_id=str(owner_id))
    return AnthropicClient(
        api_key=api_key,
        model=model or "claude-sonnet-4-5-20250929",
    )
