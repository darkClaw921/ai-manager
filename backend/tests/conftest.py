"""Shared test fixtures for the AI Manager backend.

Uses SQLite async with aiosqlite for fast, isolated tests.
Provides factory fixtures for creating test models.
"""

import os
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

import bcrypt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base import Base
from app.models.channel import Channel, ChannelType
from app.models.conversation import Conversation, ConversationStatus, Message, MessageRole, MessageType
from app.models.lead import Lead, LeadStatus
from app.models.user import AdminUser, UserRole


# ── Test settings via environment variables ─────────────────────────────

_TEST_ENV = {
    "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
    "REDIS_URL": "redis://localhost:6379/15",
    "JWT_SECRET_KEY": "test-secret-key",
    "JWT_ALGORITHM": "HS256",
    "JWT_EXPIRATION_MINUTES": "60",
    "APP_NAME": "AI Lead Manager Test",
    "DEBUG": "true",
    "LOG_LEVEL": "DEBUG",
    "TELEGRAM_BOT_TOKEN": "",
    "CELERY_BROKER_URL": "redis://localhost:6379/15",
    "CRM_WEBHOOK_URL": "",
    "GOOGLE_SHEETS_CREDENTIALS": "",
}


# ── Test database engine (SQLite async, shared in-memory) ───────────────

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False,
)

TestSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession]:
    """Provide a clean database session for each test.

    Creates all tables before the test and drops them after.
    """
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# ── Factory fixtures ────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def channel_factory(db_session: AsyncSession):
    """Factory for creating test channels."""

    async def _create(
        name: str = "Test Channel",
        channel_type: ChannelType = ChannelType.WEB_WIDGET,
        is_active: bool = True,
        config: dict | None = None,
    ) -> Channel:
        channel = Channel(
            id=uuid.uuid4(),
            name=name,
            type=channel_type,
            is_active=is_active,
            config=config or {},
        )
        db_session.add(channel)
        await db_session.flush()
        await db_session.refresh(channel)
        return channel

    return _create


@pytest_asyncio.fixture
async def lead_factory(db_session: AsyncSession, channel_factory):
    """Factory for creating test leads."""

    async def _create(
        channel: Channel | None = None,
        external_id: str | None = None,
        name: str = "Test Lead",
        status: LeadStatus = LeadStatus.NEW,
        qualification_stage: str = "initial",
        interest_score: int = 0,
    ) -> Lead:
        if channel is None:
            channel = await channel_factory()
        lead = Lead(
            id=uuid.uuid4(),
            channel_id=channel.id,
            external_id=external_id or str(uuid.uuid4()),
            name=name,
            status=status,
            qualification_stage=qualification_stage,
            qualification_data={},
            interest_score=interest_score,
        )
        db_session.add(lead)
        await db_session.flush()
        await db_session.refresh(lead)
        return lead

    return _create


@pytest_asyncio.fixture
async def conversation_factory(db_session: AsyncSession, lead_factory):
    """Factory for creating test conversations."""

    async def _create(
        lead: Lead | None = None,
        channel: Channel | None = None,
        status: ConversationStatus = ConversationStatus.ACTIVE,
    ) -> Conversation:
        if lead is None:
            lead = await lead_factory()
        conv = Conversation(
            id=uuid.uuid4(),
            lead_id=lead.id,
            channel_id=channel.id if channel else lead.channel_id,
            status=status,
            started_at=datetime.now(timezone.utc),
        )
        db_session.add(conv)
        await db_session.flush()
        await db_session.refresh(conv)
        return conv

    return _create


@pytest_asyncio.fixture
async def message_factory(db_session: AsyncSession, conversation_factory):
    """Factory for creating test messages."""

    async def _create(
        conversation: Conversation | None = None,
        role: MessageRole = MessageRole.USER,
        content: str = "Hello",
        message_type: MessageType = MessageType.TEXT,
    ) -> Message:
        if conversation is None:
            conversation = await conversation_factory()
        msg = Message(
            id=uuid.uuid4(),
            conversation_id=conversation.id,
            role=role,
            content=content,
            message_type=message_type,
            metadata_={},
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(msg)
        await db_session.flush()
        await db_session.refresh(msg)
        return msg

    return _create


@pytest_asyncio.fixture
async def admin_user_factory(db_session: AsyncSession):
    """Factory for creating test admin users."""

    async def _create(
        email: str = "test@example.com",
        password: str = "testpassword123",
        full_name: str = "Test User",
        role: UserRole = UserRole.ADMIN,
        is_active: bool = True,
    ) -> AdminUser:
        password_hash = bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")
        user = AdminUser(
            id=uuid.uuid4(),
            email=email,
            password_hash=password_hash,
            full_name=full_name,
            role=role,
            is_active=is_active,
        )
        db_session.add(user)
        await db_session.flush()
        await db_session.refresh(user)
        return user

    return _create


# ── HTTP test client ────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def app():
    """Create a FastAPI test app with test database overrides.

    Uses environment variables + cache_clear() so that ALL modules that
    call get_settings() (including those that imported it via
    ``from app.config import get_settings``) receive the test settings.
    """
    from app.config import get_settings

    # Save existing env vars and apply test overrides
    original_env = {k: os.environ.get(k) for k in _TEST_ENV}
    os.environ.update(_TEST_ENV)

    # Clear the lru_cache so every module gets fresh test settings
    get_settings.cache_clear()

    # Reset rate limiter counters so tests don't interfere with each other
    try:
        from app.rate_limit import limiter as _rate_limiter
        _rate_limiter.reset()
    except Exception:
        pass

    try:
        from app.main import create_app
        from app.dependencies import get_db

        test_app = create_app()

        # Set up polling_service stub so channel CRUD endpoints can access it
        from app.services.telegram_polling_service import TelegramPollingService
        test_app.state.polling_service = TelegramPollingService()

        async def override_get_db():
            async with test_engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            async with TestSessionLocal() as session:
                try:
                    yield session
                    await session.commit()
                except Exception:
                    await session.rollback()
                    raise

        test_app.dependency_overrides[get_db] = override_get_db

        yield test_app
    finally:
        # Restore original environment and clear cache
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


@pytest_asyncio.fixture
async def client(app) -> AsyncGenerator[AsyncClient]:
    """Provide an async HTTP client for testing FastAPI endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
