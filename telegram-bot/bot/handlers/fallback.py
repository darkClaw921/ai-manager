"""Fallback handler for non-text messages (photos, documents, stickers, etc.)."""

import logging

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def fallback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle non-text messages with a polite explanation.

    Informs the user that only text messages are currently supported.
    """
    if not update.effective_chat:
        return

    logger.debug(
        "Received non-text message from chat_id=%s",
        update.effective_chat.id,
    )

    await update.effective_chat.send_message(
        text="Пока я умею работать только с текстовыми сообщениями. "
        "Пожалуйста, напишите ваш вопрос текстом.",
    )
