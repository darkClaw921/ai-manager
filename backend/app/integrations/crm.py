"""CRM integration: abstract base + WebhookCRM + MockCRM implementations.

Strategy pattern with factory for runtime selection based on SystemSettings.
"""

import structlog
from abc import ABC, abstractmethod
from typing import Any

import httpx

logger = structlog.get_logger(__name__)

# Retry configuration
MAX_RETRIES = 3
TIMEOUT_SECONDS = 15


class BaseCRMIntegration(ABC):
    """Abstract base class for CRM integrations."""

    @abstractmethod
    async def sync_lead(self, lead_data: dict[str, Any]) -> dict[str, Any]:
        """Synchronize a lead to the CRM.

        Args:
            lead_data: Lead data dict (id, name, email, phone, company, status,
                       interest_score, qualification_data).

        Returns:
            Result dict with status and any CRM-specific response.
        """

    @abstractmethod
    async def update_lead(self, lead_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """Update a lead in the CRM.

        Args:
            lead_id: Lead UUID string.
            data: Fields to update.

        Returns:
            Result dict with status and response.
        """

    @abstractmethod
    async def check_connection(self) -> bool:
        """Check if the CRM connection is healthy.

        Returns:
            True if connection is OK, False otherwise.
        """


class WebhookCRM(BaseCRMIntegration):
    """Universal CRM adapter via webhook POST requests.

    Sends lead data as JSON to a configured webhook URL.
    Compatible with any CRM that accepts webhook payloads (Zapier, Make, n8n, etc.).
    """

    def __init__(self, webhook_url: str) -> None:
        self.webhook_url = webhook_url
        self._client = httpx.AsyncClient(timeout=TIMEOUT_SECONDS)

    async def sync_lead(self, lead_data: dict[str, Any]) -> dict[str, Any]:
        """POST lead data to the webhook URL with retry logic."""
        payload = {
            "event": "lead_sync",
            "data": lead_data,
        }
        return await self._send_with_retry(payload)

    async def update_lead(self, lead_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """POST lead update to the webhook URL."""
        payload = {
            "event": "lead_update",
            "lead_id": lead_id,
            "data": data,
        }
        return await self._send_with_retry(payload)

    async def check_connection(self) -> bool:
        """Send a ping event to verify the webhook is reachable."""
        try:
            response = await self._client.post(
                self.webhook_url,
                json={"event": "ping"},
                timeout=5,
            )
            return response.status_code < 400
        except Exception:
            logger.warning("CRM webhook connection check failed: %s", self.webhook_url)
            return False

    async def _send_with_retry(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Send payload with retry logic (up to MAX_RETRIES attempts)."""
        last_error: Exception | None = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = await self._client.post(
                    self.webhook_url,
                    json=payload,
                )
                response.raise_for_status()

                logger.info(
                    "CRM webhook call succeeded (attempt %d): %s -> %d",
                    attempt,
                    payload.get("event"),
                    response.status_code,
                )
                return {
                    "status": "success",
                    "status_code": response.status_code,
                    "response": response.text[:500],
                }
            except httpx.HTTPStatusError as exc:
                last_error = exc
                logger.warning(
                    "CRM webhook HTTP error (attempt %d/%d): %s",
                    attempt,
                    MAX_RETRIES,
                    exc,
                )
            except httpx.RequestError as exc:
                last_error = exc
                logger.warning(
                    "CRM webhook request error (attempt %d/%d): %s",
                    attempt,
                    MAX_RETRIES,
                    exc,
                )

        logger.error("CRM webhook failed after %d attempts: %s", MAX_RETRIES, last_error)
        return {
            "status": "error",
            "error": str(last_error),
            "attempts": MAX_RETRIES,
        }

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()


class MockCRM(BaseCRMIntegration):
    """Mock CRM for testing. Logs all calls and always returns success."""

    async def sync_lead(self, lead_data: dict[str, Any]) -> dict[str, Any]:
        logger.info("MockCRM.sync_lead: %s", lead_data.get("id", "unknown"))
        return {"status": "success", "mock": True, "lead_id": lead_data.get("id")}

    async def update_lead(self, lead_id: str, data: dict[str, Any]) -> dict[str, Any]:
        logger.info("MockCRM.update_lead: %s -> %s", lead_id, list(data.keys()))
        return {"status": "success", "mock": True, "lead_id": lead_id}

    async def check_connection(self) -> bool:
        logger.info("MockCRM.check_connection: OK")
        return True


def get_crm_integration(webhook_url: str | None = None) -> BaseCRMIntegration:
    """Factory: create CRM integration based on configuration.

    Args:
        webhook_url: CRM webhook URL from settings. If empty/None, returns MockCRM.

    Returns:
        BaseCRMIntegration implementation.
    """
    if webhook_url:
        logger.info("Using WebhookCRM with URL: %s", webhook_url[:50])
        return WebhookCRM(webhook_url=webhook_url)

    logger.info("No CRM webhook configured, using MockCRM")
    return MockCRM()
