"""Bot configuration loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class BotSettings(BaseSettings):
    """Telegram bot settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Telegram ---
    TELEGRAM_BOT_TOKEN: str
    WEBHOOK_URL: str = ""  # Public URL for Telegram webhook (e.g., https://example.com)
    WEBHOOK_SECRET: str = ""  # Secret token for webhook verification

    # --- Backend API ---
    BACKEND_API_URL: str = "http://api:8000"

    # --- Channel ---
    TELEGRAM_CHANNEL_ID: str = ""  # UUID of the Telegram channel in the backend DB

    # --- Logging ---
    LOG_LEVEL: str = "INFO"


@lru_cache
def get_bot_settings() -> BotSettings:
    """Return cached BotSettings instance."""
    return BotSettings()
