"""Handler for /start command -- initializes conversation with the AI agent."""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from bot.api_client import BackendAPIClient
from bot.config import get_bot_settings

logger = logging.getLogger(__name__)


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /start command.

    Initializes a conversation with the backend AI engine and sends the
    greeting message to the user.
    """
    if not update.effective_chat or not update.effective_user:
        return

    chat_id = str(update.effective_chat.id)
    user = update.effective_user
    display_name = user.first_name or user.username or None

    settings = get_bot_settings()
    api_client: BackendAPIClient = context.bot_data["api_client"]

    try:
        result = await api_client.init_conversation(
            channel_id=settings.TELEGRAM_CHANNEL_ID,
            external_id=chat_id,
            name=display_name,
        )

        # Store conversation_id in user data for subsequent messages
        context.user_data["conversation_id"] = result.get("conversation_id")
        context.user_data["lead_id"] = result.get("lead_id")

        greeting = result.get("greeting", "Здравствуйте! Чем могу помочь?")
        await update.effective_chat.send_message(text=greeting)

        logger.info(
            "Started conversation for chat_id=%s, conversation_id=%s",
            chat_id,
            result.get("conversation_id"),
        )
    except Exception:
        logger.exception("Failed to init conversation for chat_id=%s", chat_id)
        await update.effective_chat.send_message(
            text="Произошла ошибка при инициализации. Попробуйте позже.",
        )
