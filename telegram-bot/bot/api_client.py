"""HTTP client for communicating with the backend API.

The Telegram bot is a thin service -- all business logic lives on the backend.
This client sends user messages to the backend and receives AI responses.
"""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# AI may take a while to generate a response; use a generous timeout.
DEFAULT_TIMEOUT = 30.0
MAX_RETRIES = 3


class BackendAPIClient:
    """Async HTTP client for the backend API.

    Sends Telegram user messages to the backend's webhook endpoints and
    receives AI-generated responses.
    """

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=DEFAULT_TIMEOUT,
        )

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    async def init_conversation(
        self,
        channel_id: str,
        external_id: str,
        name: str | None = None,
    ) -> dict[str, Any]:
        """Initialize or retrieve a conversation for a Telegram user.

        POST /api/v1/webhooks/telegram/{channel_id}/init

        Args:
            channel_id: UUID of the Telegram channel in the backend DB.
            external_id: Telegram user/chat ID.
            name: Optional display name of the user.

        Returns:
            Dict with keys: conversation_id, lead_id, greeting.
        """
        payload: dict[str, Any] = {"external_id": external_id}
        if name:
            payload["name"] = name

        return await self._post(
            f"/api/v1/webhooks/telegram/{channel_id}/init",
            payload,
        )

    async def send_message(
        self,
        channel_id: str,
        external_id: str,
        text: str,
    ) -> dict[str, Any]:
        """Send a user message and receive the AI response.

        POST /api/v1/webhooks/telegram/{channel_id}

        Args:
            channel_id: UUID of the Telegram channel.
            external_id: Telegram user/chat ID.
            text: User message text.

        Returns:
            Dict with keys: text, actions, qualification_stage, interest_score.
        """
        payload = {
            "external_id": external_id,
            "text": text,
        }

        return await self._post(
            f"/api/v1/webhooks/telegram/{channel_id}",
            payload,
        )

    async def get_conversation_status(self, conversation_id: str) -> dict[str, Any]:
        """Get the current status of a conversation.

        GET /api/v1/webhooks/telegram/conversations/{conversation_id}/status

        Args:
            conversation_id: UUID of the conversation.

        Returns:
            Dict with conversation status info.
        """
        return await self._get(
            f"/api/v1/webhooks/telegram/conversations/{conversation_id}/status",
        )

    # ------------------------------------------------------------------
    # Internal helpers with retry
    # ------------------------------------------------------------------

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        """POST with retry on network errors."""
        last_exc: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = await self._client.post(path, json=payload)
                response.raise_for_status()
                return response.json()
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout) as exc:
                last_exc = exc
                logger.warning(
                    "POST %s attempt %d/%d failed: %s",
                    path,
                    attempt,
                    MAX_RETRIES,
                    exc,
                )
            except httpx.HTTPStatusError as exc:
                # Do not retry on 4xx/5xx -- propagate immediately
                logger.error(
                    "POST %s returned %d: %s",
                    path,
                    exc.response.status_code,
                    exc.response.text,
                )
                raise

        logger.error(
            "POST %s failed after %d retries: %s",
            path,
            MAX_RETRIES,
            last_exc,
        )
        raise last_exc  # type: ignore[misc]

    async def _get(self, path: str) -> dict[str, Any]:
        """GET with retry on network errors."""
        last_exc: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = await self._client.get(path)
                response.raise_for_status()
                return response.json()
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout) as exc:
                last_exc = exc
                logger.warning(
                    "GET %s attempt %d/%d failed: %s",
                    path,
                    attempt,
                    MAX_RETRIES,
                    exc,
                )
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "GET %s returned %d: %s",
                    path,
                    exc.response.status_code,
                    exc.response.text,
                )
                raise

        logger.error(
            "GET %s failed after %d retries: %s",
            path,
            MAX_RETRIES,
            last_exc,
        )
        raise last_exc  # type: ignore[misc]
