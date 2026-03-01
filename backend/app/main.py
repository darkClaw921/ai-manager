from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.config import get_settings
from app.logging_config import setup_logging
from app.middleware import RequestLoggingMiddleware
from app.rate_limit import limiter, rate_limit_exceeded_handler

# Initialize structured logging before anything else
setup_logging()

logger = structlog.get_logger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown logic."""
    # --- Startup ---
    logger.info("app_starting", app_name=settings.APP_NAME)

    # Check database connection
    try:
        from app.db.session import engine

        async with engine.connect() as conn:
            await conn.execute(
                __import__("sqlalchemy").text("SELECT 1")
            )
        logger.info("service_connected", service="postgres")
    except Exception as e:
        logger.error("service_connection_failed", service="postgres", error=str(e))

    # Check Redis connection
    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(settings.REDIS_URL)
        await r.ping()
        await r.aclose()
        logger.info("service_connected", service="redis")
    except Exception as e:
        logger.warning("service_connection_failed", service="redis", error=str(e))

    # Check Qdrant connection and ensure collections
    try:
        from qdrant_client import AsyncQdrantClient

        qdrant = AsyncQdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
        await qdrant.get_collections()
        logger.info("service_connected", service="qdrant")

        # Ensure Qdrant collections exist
        from app.ai.qdrant_init import ensure_collections

        await ensure_collections(qdrant)
        logger.info("qdrant_collections_initialized")

        await qdrant.close()
    except Exception as e:
        logger.warning("service_connection_failed", service="qdrant", error=str(e))

    # Initialize polling service and register Telegram channels (webhook or polling)
    from app.services.telegram_polling_service import TelegramPollingService

    polling_service = TelegramPollingService()
    app.state.polling_service = polling_service

    try:
        from sqlalchemy import select as sa_select

        from app.db.session import async_session_factory
        from app.models.channel import Channel, ChannelType
        from app.services.telegram_webhook_service import TelegramWebhookService

        async with async_session_factory() as session:
            result = await session.execute(
                sa_select(Channel).where(
                    Channel.type == ChannelType.TELEGRAM,
                    Channel.is_active.is_(True),
                )
            )
            channels = result.scalars().all()

            if channels:
                webhook_service: TelegramWebhookService | None = None
                try:
                    for ch in channels:
                        config = dict(ch.config or {})
                        bot_token = config.get("bot_token", "")
                        if not bot_token:
                            continue

                        bot_mode = config.get("bot_mode", "webhook")

                        if bot_mode == "polling":
                            await polling_service.start_polling(ch.id, bot_token)
                            logger.info(
                                "telegram_channel_mode",
                                channel_id=str(ch.id),
                                mode="polling",
                            )
                        elif bot_mode == "webhook":
                            if not settings.WEBHOOK_BASE_URL:
                                logger.warning(
                                    "webhook_base_url_not_set",
                                    channel_id=str(ch.id),
                                    detail="Cannot register webhook without WEBHOOK_BASE_URL, skipping",
                                )
                                continue

                            if webhook_service is None:
                                webhook_service = TelegramWebhookService()

                            webhook_secret = config.get("webhook_secret") or TelegramWebhookService.generate_webhook_secret()
                            webhook_url = f"{settings.WEBHOOK_BASE_URL.rstrip('/')}/api/v1/webhooks/telegram/{ch.id}/update"

                            wh_result = await webhook_service.set_webhook(bot_token, webhook_url, webhook_secret)
                            if wh_result.get("ok"):
                                config["webhook_secret"] = webhook_secret
                                config["webhook_url"] = webhook_url
                                ch.config = config
                                logger.info(
                                    "telegram_channel_mode",
                                    channel_id=str(ch.id),
                                    mode="webhook",
                                )
                            else:
                                logger.error("telegram_webhook_failed", channel_id=str(ch.id))
                        else:
                            logger.warning(
                                "unknown_bot_mode",
                                channel_id=str(ch.id),
                                bot_mode=bot_mode,
                            )

                    await session.commit()
                finally:
                    if webhook_service is not None:
                        await webhook_service.close()

                logger.info("telegram_channels_initialized", count=len(channels))
    except Exception as e:
        logger.warning("telegram_channel_init_failed", error=str(e))

    yield

    # --- Shutdown ---
    logger.info("app_shutting_down", app_name=settings.APP_NAME)

    await app.state.polling_service.stop_all()
    logger.info("polling_tasks_stopped")

    from app.db.session import engine

    await engine.dispose()
    logger.info("database_connections_closed")


def create_app() -> FastAPI:
    """FastAPI application factory."""
    app = FastAPI(
        title=settings.APP_NAME,
        version="0.1.0",
        lifespan=lifespan,
    )

    # Request logging middleware (outer — runs first)
    app.add_middleware(RequestLoggingMiddleware)

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Rate limiting
    from slowapi.errors import RateLimitExceeded

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

    # Health check with service status
    @app.get("/health")
    async def health_check():
        services: dict[str, str] = {}
        overall_status = "ok"

        # Check PostgreSQL
        try:
            from app.db.session import engine as db_engine
            async with db_engine.connect() as conn:
                await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
            services["postgres"] = "ok"
        except Exception:
            services["postgres"] = "error"
            overall_status = "degraded"

        # Check Redis
        try:
            import redis.asyncio as aioredis
            r = aioredis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
            await r.ping()
            await r.aclose()
            services["redis"] = "ok"
        except Exception:
            services["redis"] = "error"
            overall_status = "degraded"

        # Check Qdrant
        try:
            from qdrant_client import AsyncQdrantClient
            qdrant = AsyncQdrantClient(
                host=settings.QDRANT_HOST, port=settings.QDRANT_PORT, timeout=2,
            )
            await qdrant.get_collections()
            await qdrant.close()
            services["qdrant"] = "ok"
        except Exception:
            services["qdrant"] = "error"
            overall_status = "degraded"

        return {
            "status": overall_status,
            "services": services,
            "version": "0.1.0",
        }

    # Include API router
    app.include_router(api_router, prefix="/api/v1")

    return app


app = create_app()
