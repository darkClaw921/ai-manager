"""Pydantic schemas for API request/response."""

from app.schemas.analytics import DashboardResponse, FunnelResponse, FunnelStage, LeadStatsResponse
from app.schemas.auth import LoginRequest, RefreshRequest, TokenResponse
from app.schemas.booking import BookingCreate, BookingResponse, BookingSettingsResponse, BookingSettingsUpdate, BookingUpdate
from app.schemas.channel import ChannelCreate, ChannelResponse, ChannelUpdate
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.conversation import (
    ConversationDetailResponse,
    ConversationFilter,
    ConversationResponse,
    ConversationStatusUpdate,
    MessageResponse,
)
from app.schemas.lead import LeadFilter, LeadResponse, LeadUpdateRequest
from app.schemas.messages import IncomingMessageSchema, OutgoingMessageSchema
from app.schemas.script import (
    FAQItemCreate,
    FAQItemResponse,
    FAQItemUpdate,
    ObjectionScriptCreate,
    ObjectionScriptResponse,
    ObjectionScriptUpdate,
    QualificationScriptCreate,
    QualificationScriptResponse,
    QualificationScriptUpdate,
)
from app.schemas.settings import SystemSettingsResponse, SystemSettingsUpdate
from app.schemas.user import UserCreate, UserResponse, UserUpdate

__all__ = [
    # Auth
    "LoginRequest",
    "RefreshRequest",
    "TokenResponse",
    # User
    "UserCreate",
    "UserResponse",
    "UserUpdate",
    # Lead
    "LeadResponse",
    "LeadUpdateRequest",
    "LeadFilter",
    # Conversation
    "ConversationResponse",
    "ConversationDetailResponse",
    "ConversationStatusUpdate",
    "ConversationFilter",
    "MessageResponse",
    # Script
    "QualificationScriptCreate",
    "QualificationScriptUpdate",
    "QualificationScriptResponse",
    "FAQItemCreate",
    "FAQItemUpdate",
    "FAQItemResponse",
    "ObjectionScriptCreate",
    "ObjectionScriptUpdate",
    "ObjectionScriptResponse",
    # Channel
    "ChannelCreate",
    "ChannelUpdate",
    "ChannelResponse",
    # Booking
    "BookingCreate",
    "BookingUpdate",
    "BookingResponse",
    "BookingSettingsUpdate",
    "BookingSettingsResponse",
    # Settings
    "SystemSettingsResponse",
    "SystemSettingsUpdate",
    # Analytics
    "DashboardResponse",
    "LeadStatsResponse",
    "FunnelResponse",
    "FunnelStage",
    # Common
    "PaginationParams",
    "PaginatedResponse",
    # Messages
    "IncomingMessageSchema",
    "OutgoingMessageSchema",
]
