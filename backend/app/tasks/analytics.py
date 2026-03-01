"""Celery tasks for analytics and conversation monitoring.

- Daily analytics calculation and optional export to Google Sheets.
- Stale conversation detection with webhook notifications.
"""

import asyncio
import structlog
from datetime import datetime, timedelta, timezone

from app.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)

# Conversations active longer than this threshold are considered stale
STALE_CONVERSATION_HOURS = 24


async def _calculate_daily_analytics_async() -> dict:
    """Async implementation of daily analytics calculation."""
    from sqlalchemy import func, select

    from app.config import get_settings
    from app.db.session import get_db_session
    from app.integrations.google_sheets import GoogleSheetsExporter
    from app.models.booking import Booking
    from app.models.lead import Lead, LeadStatus

    settings = get_settings()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today_start - timedelta(days=1)

    async with get_db_session() as db:
        # Total leads
        total_leads = (await db.execute(
            select(func.count()).select_from(Lead)
        )).scalar_one()

        # Leads created yesterday (the day we're calculating for)
        new_yesterday = (await db.execute(
            select(func.count()).select_from(Lead).where(
                Lead.created_at >= yesterday_start,
                Lead.created_at < today_start,
            )
        )).scalar_one()

        # Qualified leads
        qualified_count = (await db.execute(
            select(func.count()).select_from(Lead).where(
                Lead.status.in_([
                    LeadStatus.QUALIFIED,
                    LeadStatus.BOOKED,
                    LeadStatus.HANDED_OFF,
                ])
            )
        )).scalar_one()

        # Bookings count
        bookings_count = (await db.execute(
            select(func.count()).select_from(Booking)
        )).scalar_one()

        # Average interest score
        avg_score_result = (await db.execute(
            select(func.avg(Lead.interest_score)).where(Lead.interest_score > 0)
        )).scalar_one()
        avg_score = round(float(avg_score_result), 1) if avg_score_result else 0.0

        # Qualification rate
        qualification_rate = round(qualified_count / total_leads * 100, 1) if total_leads > 0 else 0.0

        analytics_data = {
            "date": yesterday_start.strftime("%Y-%m-%d"),
            "total_leads": total_leads,
            "new_today": new_yesterday,
            "qualified_count": qualified_count,
            "bookings_count": bookings_count,
            "avg_score": avg_score,
            "qualification_rate": qualification_rate,
        }

        logger.info("Daily analytics calculated: %s", analytics_data)

        # Export to Google Sheets if configured
        if settings.GOOGLE_SHEETS_CREDENTIALS:
            try:
                # Read spreadsheet_id from system settings
                from sqlalchemy import select as sel

                from app.models.settings import SystemSettings

                sheets_setting = (await db.execute(
                    sel(SystemSettings).where(SystemSettings.key == "google_sheets_spreadsheet_id")
                )).scalar_one_or_none()

                spreadsheet_id = ""
                if sheets_setting and sheets_setting.value:
                    spreadsheet_id = sheets_setting.value.get("value", "") if isinstance(sheets_setting.value, dict) else str(sheets_setting.value)

                if spreadsheet_id:
                    exporter = GoogleSheetsExporter(
                        credentials_json=settings.GOOGLE_SHEETS_CREDENTIALS,
                        spreadsheet_id=spreadsheet_id,
                    )
                    exported = await exporter.export_analytics(analytics_data)
                    logger.info("Exported analytics to Google Sheets: %d rows", exported)
            except Exception:
                logger.exception("Failed to export analytics to Google Sheets")

        return analytics_data


async def _check_stale_conversations_async() -> int:
    """Async implementation of stale conversation detection."""
    from sqlalchemy import select

    from app.config import get_settings
    from app.db.session import get_db_session
    from app.integrations.webhook_notifier import WebhookNotifier
    from app.models.conversation import Conversation, ConversationStatus

    settings = get_settings()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    stale_threshold = now - timedelta(hours=STALE_CONVERSATION_HOURS)

    async with get_db_session() as db:
        # Find active conversations older than threshold
        result = await db.execute(
            select(Conversation).where(
                Conversation.status == ConversationStatus.ACTIVE,
                Conversation.started_at < stale_threshold,
            )
        )
        stale_conversations = list(result.scalars().all())

        if not stale_conversations:
            logger.debug("No stale conversations found")
            return 0

        logger.warning("Found %d stale conversations", len(stale_conversations))

        # Send notifications for stale conversations
        notifier = WebhookNotifier(
            webhook_url=settings.CRM_WEBHOOK_URL or None,
            telegram_bot_token=settings.TELEGRAM_BOT_TOKEN or None,
        )

        try:
            for conv in stale_conversations:
                await notifier.notify_handoff({
                    "id": str(conv.id),
                    "lead_name": "Зависший диалог",
                    "lead_id": str(conv.lead_id),
                    "reason": "stale_conversation",
                    "started_at": conv.started_at.isoformat() if conv.started_at else "",
                })
        finally:
            await notifier.close()

        return len(stale_conversations)


@celery_app.task(
    name="app.tasks.analytics.calculate_daily_analytics",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
)
def calculate_daily_analytics(self) -> dict:
    """Calculate and store daily analytics.

    Periodic task: runs daily at 00:00 UTC via Beat schedule.
    Optionally exports to Google Sheets if configured.

    Returns:
        Analytics data dict.
    """
    try:
        return asyncio.run(_calculate_daily_analytics_async())
    except Exception as exc:
        logger.exception("Daily analytics calculation failed")
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.tasks.analytics.check_stale_conversations",
    bind=True,
    max_retries=1,
    default_retry_delay=60,
)
def check_stale_conversations(self) -> int:
    """Check for stale (stuck) conversations and send notifications.

    Periodic task: runs every hour via Beat schedule.
    A conversation is considered stale if it has been active for more than
    STALE_CONVERSATION_HOURS hours without completion.

    Returns:
        Number of stale conversations found.
    """
    try:
        return asyncio.run(_check_stale_conversations_async())
    except Exception as exc:
        logger.exception("Stale conversation check failed")
        raise self.retry(exc=exc)
