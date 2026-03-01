"""Handler for regular text messages -- sends them to the AI engine."""

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot.api_client import BackendAPIClient
from bot.config import get_bot_settings

logger = logging.getLogger(__name__)


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming text messages.

    Sends the user's message to the backend AI engine and relays
    the response back to the Telegram chat.
    """
    if not update.message or not update.message.text or not update.effective_chat:
        return

    chat_id = str(update.effective_chat.id)
    user_text = update.message.text

    settings = get_bot_settings()
    api_client: BackendAPIClient = context.bot_data["api_client"]

    # If no conversation_id, auto-initialize (user may have skipped /start)
    if not context.user_data.get("conversation_id"):
        user = update.effective_user
        display_name = user.first_name if user else None
        try:
            init_result = await api_client.init_conversation(
                channel_id=settings.TELEGRAM_CHANNEL_ID,
                external_id=chat_id,
                name=display_name,
            )
            context.user_data["conversation_id"] = init_result.get("conversation_id")
            context.user_data["lead_id"] = init_result.get("lead_id")
        except Exception:
            logger.exception("Auto-init failed for chat_id=%s", chat_id)
            await update.effective_chat.send_message(
                text="Произошла ошибка. Попробуйте начать с /start",
            )
            return

    try:
        result = await api_client.send_message(
            channel_id=settings.TELEGRAM_CHANNEL_ID,
            external_id=chat_id,
            text=user_text,
        )

        ai_text = result.get("text", "")
        actions = result.get("actions", [])

        # Send the AI response
        if ai_text:
            await update.effective_chat.send_message(text=ai_text)

        # Handle actions from the AI engine
        await _handle_actions(update, context, actions)

    except Exception:
        logger.exception("Failed to process message for chat_id=%s", chat_id)
        await update.effective_chat.send_message(
            text="Извините, произошла ошибка. Попробуйте ещё раз.",
        )


async def booking_callback_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle inline keyboard button presses for booking slots.

    Callback data format: book:{date}:{time}
    """
    query = update.callback_query
    if not query or not query.data:
        return

    await query.answer()

    if not query.data.startswith("book:"):
        return

    parts = query.data.split(":")
    if len(parts) != 3:
        return

    _, slot_date, slot_time = parts

    # Acknowledge the selection
    await query.edit_message_text(
        text=f"Вы выбрали: {slot_date} в {slot_time}. Записываю вас...",
    )

    # Send the booking selection back to the AI as a text message
    chat_id = str(query.message.chat.id) if query.message else ""
    settings = get_bot_settings()
    api_client: BackendAPIClient = context.bot_data["api_client"]

    try:
        result = await api_client.send_message(
            channel_id=settings.TELEGRAM_CHANNEL_ID,
            external_id=chat_id,
            text=f"Записываюсь на {slot_date} в {slot_time}",
        )

        ai_text = result.get("text", "")
        if ai_text and query.message:
            await query.message.reply_text(text=ai_text)

    except Exception:
        logger.exception("Failed to process booking callback for chat_id=%s", chat_id)
        if query.message:
            await query.message.reply_text(
                text="Произошла ошибка при записи. Попробуйте ещё раз.",
            )


async def _handle_actions(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    actions: list[dict],
) -> None:
    """Process actions returned by the AI engine.

    Supported action names:
        - booking: send inline keyboard with booking slots
        - transfer: notify user about handoff to a manager
    """
    if not update.effective_chat:
        return

    for action in actions:
        action_name = action.get("name", "")
        details = action.get("details", {})

        if action_name == "booking":
            slots = details.get("slots", [])
            if slots:
                keyboard = _build_booking_keyboard(slots)
                await update.effective_chat.send_message(
                    text="Выберите удобное время для консультации:",
                    reply_markup=keyboard,
                )
            else:
                await update.effective_chat.send_message(
                    text="К сожалению, нет доступных слотов. Менеджер свяжется с вами.",
                )

        elif action_name == "transfer":
            await update.effective_chat.send_message(
                text="Ваш диалог передан менеджеру. Он свяжется с вами в ближайшее время.",
            )


def _build_booking_keyboard(slots: list[dict]) -> InlineKeyboardMarkup:
    """Build an InlineKeyboardMarkup from booking slots.

    Each slot should have 'date' and 'time' keys.
    Buttons are arranged in rows of 2.
    """
    buttons: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []

    for slot in slots:
        slot_date = slot.get("date", "")
        slot_time = slot.get("time", "")
        label = f"{slot_date} {slot_time}"
        callback_data = f"book:{slot_date}:{slot_time}"

        row.append(InlineKeyboardButton(text=label, callback_data=callback_data))
        if len(row) == 2:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    return InlineKeyboardMarkup(buttons)
