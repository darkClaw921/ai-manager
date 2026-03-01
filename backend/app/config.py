from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- App ---
    APP_NAME: str = "AI Lead Manager"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # --- Database ---
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@postgres:5432/ai_manager"

    # --- Redis ---
    REDIS_URL: str = "redis://redis:6379/0"

    # --- Qdrant ---
    QDRANT_HOST: str = "qdrant"
    QDRANT_PORT: int = 6333

    # --- JWT ---
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_MINUTES: int = 60

    # --- Telegram ---
    WEBHOOK_BASE_URL: str = ""  # Public URL for Telegram webhook registration (e.g., https://example.com)

    # --- CORS ---
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:3001"]

    # --- Celery ---
    CELERY_BROKER_URL: str = "redis://redis:6379/1"

    # --- Integrations (optional) ---
    CRM_WEBHOOK_URL: str = ""
    GOOGLE_SHEETS_CREDENTIALS: str = ""


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings instance."""
    return Settings()
