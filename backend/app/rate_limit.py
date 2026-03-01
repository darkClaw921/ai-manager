"""Rate limiting configuration using slowapi with Redis backend.

Provides a configured Limiter instance and custom error handler.
Different limits for different endpoint groups:
- Widget messages: 30/minute per IP
- Login: 5/minute per IP (brute-force protection)
- Webhooks: 60/minute per channel
- General API: 100/minute per user
"""

import structlog
from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import get_settings

logger = structlog.get_logger(__name__)


def _get_key_func(request: Request) -> str:
    """Default key function: use remote IP address."""
    return get_remote_address(request)


def create_limiter() -> Limiter:
    """Create and configure the rate limiter with Redis backend."""
    settings = get_settings()
    return Limiter(
        key_func=_get_key_func,
        storage_uri=settings.REDIS_URL,
        default_limits=["100/minute"],
        headers_enabled=False,
    )


limiter = create_limiter()


async def rate_limit_exceeded_handler(
    request: Request, exc: RateLimitExceeded
) -> JSONResponse:
    """Custom 429 error handler with Retry-After header and structured logging."""
    logger.warning(
        "rate_limit_exceeded",
        client_ip=get_remote_address(request),
        path=request.url.path,
        method=request.method,
        limit=str(exc.detail),
    )

    # Extract retry-after from the exception detail
    retry_after = getattr(exc, "retry_after", 60)

    return JSONResponse(
        status_code=429,
        content={
            "detail": "Too many requests. Please slow down.",
            "retry_after": retry_after,
        },
        headers={"Retry-After": str(retry_after)},
    )
