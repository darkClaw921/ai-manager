"""API router aggregator: registers all endpoint routers under /api/v1."""

from fastapi import APIRouter

from app.api import analytics, auth, bookings, channels, conversations, leads, managers, scripts, settings, users, webhooks, widget

api_router = APIRouter()

# Auth (no JWT required for login/refresh)
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])

# Admin panel CRUD endpoints (JWT required)
api_router.include_router(leads.router, prefix="/leads", tags=["leads"])
api_router.include_router(conversations.router, prefix="/conversations", tags=["conversations"])
api_router.include_router(scripts.router, prefix="/scripts", tags=["scripts"])
api_router.include_router(channels.router, prefix="/channels", tags=["channels"])
api_router.include_router(bookings.router, prefix="/bookings", tags=["bookings"])
api_router.include_router(settings.router, prefix="/settings", tags=["settings"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(managers.router, prefix="/managers", tags=["managers"])

# Widget endpoints (WebSocket + REST)
api_router.include_router(widget.router, prefix="/widget", tags=["widget"])

# Webhook endpoints (Telegram)
api_router.include_router(webhooks.router)
