"""Structured logging configuration using structlog.

JSON output for production, ConsoleRenderer for development.
Integrates with stdlib logging (uvicorn, sqlalchemy, etc.).
"""

import logging
import sys

import structlog

from app.config import get_settings


def setup_logging() -> None:
    """Configure structlog and stdlib logging.

    In production (non-TTY), outputs JSON for machine parsing.
    In development (TTY), outputs pretty console format.
    """
    settings = get_settings()
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    # Shared processors for both structlog and stdlib.
    # NOTE: filter_by_level is intentionally excluded here because:
    # - stdlib logs go through level filtering before reaching ProcessorFormatter
    # - filter_by_level accesses logger.disabled which can be None during shutdown
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    if sys.stderr.isatty() and settings.DEBUG:
        # Development: pretty console output
        renderer: structlog.types.Processor = structlog.dev.ConsoleRenderer()
    else:
        # Production: JSON output
        shared_processors.append(
            structlog.processors.CallsiteParameterAdder(
                {
                    structlog.processors.CallsiteParameter.FILENAME,
                    structlog.processors.CallsiteParameter.FUNC_NAME,
                    structlog.processors.CallsiteParameter.LINENO,
                }
            )
        )
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[structlog.stdlib.filter_by_level, *shared_processors, renderer],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure stdlib root logger so uvicorn/sqlalchemy logs also go through structlog
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers to avoid duplicate output
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)

    # Use structlog formatter for stdlib logs
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        foreign_pre_chain=shared_processors,
    )
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    # Quieten noisy loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.DEBUG if settings.DEBUG else logging.WARNING
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
