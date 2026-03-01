"""Celery tasks for CRM synchronization.

Syncs leads to the configured CRM when they reach qualified/booked status.
"""

import asyncio
import structlog

from app.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)


async def _sync_lead_async(lead_id: str) -> dict:
    """Async implementation of lead-to-CRM sync."""
    from sqlalchemy import select

    from app.config import get_settings
    from app.db.session import get_db_session
    from app.integrations.crm import get_crm_integration
    from app.models.lead import Lead

    settings = get_settings()
    crm = get_crm_integration(webhook_url=settings.CRM_WEBHOOK_URL or None)

    async with get_db_session() as db:
        result = await db.execute(select(Lead).where(Lead.id == lead_id))
        lead = result.scalar_one_or_none()

        if lead is None:
            logger.warning("CRM sync: lead %s not found", lead_id)
            return {"status": "error", "error": "lead_not_found"}

        lead_data = {
            "id": str(lead.id),
            "name": lead.name,
            "email": lead.email,
            "phone": lead.phone,
            "company": lead.company,
            "status": lead.status.value if lead.status else None,
            "interest_score": lead.interest_score,
            "qualification_stage": lead.qualification_stage,
            "qualification_data": lead.qualification_data,
            "source": lead.source,
        }

        sync_result = await crm.sync_lead(lead_data)

        # Update lead metadata with sync result
        metadata = lead.metadata_ or {}
        metadata["crm_sync"] = {
            "status": sync_result.get("status"),
            "synced_at": asyncio.get_event_loop().time(),
        }
        lead.metadata_ = metadata

        logger.info(
            "CRM sync completed for lead %s: %s",
            lead_id,
            sync_result.get("status"),
        )
        return sync_result


@celery_app.task(
    name="app.tasks.crm_sync.sync_lead_to_crm",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def sync_lead_to_crm(self, lead_id: str) -> dict:
    """Synchronize a lead to the configured CRM integration.

    Called when lead reaches qualified, booked, or handed_off status.

    Args:
        lead_id: UUID string of the lead.

    Returns:
        Sync result dict.
    """
    try:
        return asyncio.run(_sync_lead_async(lead_id))
    except Exception as exc:
        logger.exception("CRM sync failed for lead %s", lead_id)
        raise self.retry(exc=exc)
