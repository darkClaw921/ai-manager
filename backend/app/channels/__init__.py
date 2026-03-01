from app.channels.base import AbstractChannelAdapter, IncomingMessage
from app.channels.telegram import TelegramAdapter
from app.channels.web_widget import WebWidgetAdapter

__all__ = [
    "AbstractChannelAdapter",
    "IncomingMessage",
    "TelegramAdapter",
    "WebWidgetAdapter",
]
