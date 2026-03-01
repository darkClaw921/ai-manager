"""Telegram bot entry point -- Application setup with webhook mode."""

import logging

from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from bot.api_client import BackendAPIClient
from bot.config import get_bot_settings
from bot.handlers.conversation import booking_callback_handler, message_handler
from bot.handlers.fallback import fallback_handler
from bot.handlers.start import start_handler
from bot.health import start_health_server

logger = logging.getLogger(__name__)


async def post_init(application: Application) -> None:
    """Initialize shared resources after the Application is built.

    Creates the BackendAPIClient and stores it in bot_data so handlers
    can access it via context.bot_data["api_client"].
    """
    settings = get_bot_settings()
    api_client = BackendAPIClient(base_url=settings.BACKEND_API_URL)
    application.bot_data["api_client"] = api_client

    logger.info(
        "Bot initialized. Backend: %s, Webhook: %s",
        settings.BACKEND_API_URL,
        settings.WEBHOOK_URL,
    )


async def post_shutdown(application: Application) -> None:
    """Clean up resources on shutdown.

    Closes the httpx client used by BackendAPIClient.
    """
    api_client: BackendAPIClient | None = application.bot_data.get("api_client")
    if api_client:
        await api_client.close()
        logger.info("API client closed.")


def main() -> None:
    """Build and run the Telegram bot application in webhook mode."""
    settings = get_bot_settings()

    # Configure logging
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    )

    # Start health check server for Docker healthchecks
    start_health_server(port=8080)

    logger.info("Starting Telegram bot...")
    logger.info("Token: %s...%s", settings.TELEGRAM_BOT_TOKEN[:4], settings.TELEGRAM_BOT_TOKEN[-4:])
    logger.info("Webhook URL: %s", settings.WEBHOOK_URL)
    logger.info("Backend API URL: %s", settings.BACKEND_API_URL)

    # Build application
    application = (
        Application.builder()
        .token(settings.TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    # Register handlers (order matters: more specific first)
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CallbackQueryHandler(booking_callback_handler, pattern=r"^book:"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    application.add_handler(MessageHandler(~filters.TEXT & ~filters.COMMAND, fallback_handler))

    # Run in webhook mode if WEBHOOK_URL is set, otherwise use polling
    if settings.WEBHOOK_URL:
        logger.info("Running in webhook mode")
        application.run_webhook(
            listen="0.0.0.0",
            port=8443,
            url_path="/webhook",
            webhook_url=f"{settings.WEBHOOK_URL}/webhook",
            secret_token=settings.WEBHOOK_SECRET,
        )
    else:
        logger.info("WEBHOOK_URL not set — running in polling mode")
        application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
