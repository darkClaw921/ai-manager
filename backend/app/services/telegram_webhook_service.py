"""Service for managing Telegram Bot API webhooks.

Provides methods to register/deregister webhooks, validate bot tokens,
and answer callback queries via the Telegram Bot HTTP API.
"""

import secrets

import httpx
import structlog

logger = structlog.get_logger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org"


class TelegramWebhookService:
    """Manages Telegram Bot API webhook lifecycle."""

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=45.0)

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def set_webhook(
        self,
        bot_token: str,
        webhook_url: str,
        secret_token: str,
    ) -> dict:
        """Register a webhook URL with Telegram Bot API.

        Args:
            bot_token: Telegram bot token.
            webhook_url: Public URL where Telegram will send updates.
            secret_token: Secret token for X-Telegram-Bot-Api-Secret-Token header verification.

        Returns:
            Telegram API response dict.
        """
        return await self._api_request(bot_token, "setWebhook", {
            "url": webhook_url,
            "secret_token": secret_token,
            "allowed_updates": ["message", "callback_query"],
        })

    async def delete_webhook(self, bot_token: str) -> dict:
        """Remove the webhook for a bot.

        Args:
            bot_token: Telegram bot token.

        Returns:
            Telegram API response dict.
        """
        return await self._api_request(bot_token, "deleteWebhook", {})

    async def get_updates(
        self,
        bot_token: str,
        offset: int | None = None,
        timeout: int = 30,
        limit: int = 100,
        allowed_updates: list[str] | None = None,
    ) -> dict:
        """Fetch pending updates via long polling (getUpdates).

        Args:
            bot_token: Telegram bot token.
            offset: Identifier of the first update to be returned.
            timeout: Long-poll timeout in seconds (server-side wait).
            limit: Maximum number of updates to retrieve (1-100).
            allowed_updates: List of update types to receive.

        Returns:
            Telegram API response dict with ``result`` list of updates.
        """
        payload: dict = {"timeout": timeout, "limit": limit}
        if offset is not None:
            payload["offset"] = offset
        if allowed_updates:
            payload["allowed_updates"] = allowed_updates
        return await self._api_request(bot_token, "getUpdates", payload)

    async def get_me(self, bot_token: str) -> dict:
        """Call getMe to validate a bot token and get bot info.

        Args:
            bot_token: Telegram bot token.

        Returns:
            Telegram API response dict with bot info.
        """
        return await self._api_request(bot_token, "getMe", {})

    async def answer_callback_query(
        self,
        bot_token: str,
        callback_query_id: str,
        text: str = "",
    ) -> dict:
        """Answer a callback query (acknowledge inline button press).

        Args:
            bot_token: Telegram bot token.
            callback_query_id: ID of the callback query to answer.
            text: Optional notification text shown to the user.

        Returns:
            Telegram API response dict.
        """
        payload: dict = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text
        return await self._api_request(bot_token, "answerCallbackQuery", payload)

    @staticmethod
    def generate_webhook_secret() -> str:
        """Generate a cryptographically secure webhook secret token."""
        return secrets.token_urlsafe(32)

    async def _api_request(self, bot_token: str, method: str, payload: dict) -> dict:
        """Make a POST request to the Telegram Bot API.

        Args:
            bot_token: Telegram bot token.
            method: API method name (e.g., "setWebhook").
            payload: Request body as dict.

        Returns:
            Parsed JSON response dict.
        """
        url = f"{TELEGRAM_API_BASE}/bot{bot_token}/{method}"
        try:
            response = await self._client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            if not data.get("ok"):
                logger.error(
                    "telegram_api_error",
                    method=method,
                    description=data.get("description", "unknown error"),
                )
            return data
        except httpx.HTTPStatusError as exc:
            logger.error(
                "telegram_api_http_error",
                method=method,
                status_code=exc.response.status_code,
                response_text=exc.response.text,
            )
            raise
        except httpx.RequestError as exc:
            logger.error("telegram_api_request_error", method=method, error=str(exc))
            raise
