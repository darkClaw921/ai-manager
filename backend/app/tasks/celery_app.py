"""Celery application configuration.

Redis broker, Beat schedule for periodic tasks, autodiscover for modularity.
"""

from celery import Celery
from celery.schedules import crontab

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "ai_manager",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_BROKER_URL,
    include=[
        "app.tasks.crm_sync",
        "app.tasks.qdrant_sync",
        "app.tasks.analytics",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_retry_delay=60,
    task_max_retries=3,
)

# Beat schedule: periodic tasks
celery_app.conf.beat_schedule = {
    "qdrant-sync-every-5-minutes": {
        "task": "app.tasks.qdrant_sync.sync_faq_collection",
        "schedule": 300.0,  # every 5 minutes
    },
    "qdrant-objections-sync-every-5-minutes": {
        "task": "app.tasks.qdrant_sync.sync_objections_collection",
        "schedule": 300.0,  # every 5 minutes
    },
    "analytics-daily-midnight": {
        "task": "app.tasks.analytics.calculate_daily_analytics",
        "schedule": crontab(hour=0, minute=0),  # every day at 00:00 UTC
    },
    "stale-conversations-every-hour": {
        "task": "app.tasks.analytics.check_stale_conversations",
        "schedule": 3600.0,  # every hour
    },
}

# Autodiscover tasks from registered modules
celery_app.autodiscover_tasks(["app.tasks"])
