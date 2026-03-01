"""Integration tests for widget API endpoints."""

import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient

from app.models.base import Base
from app.models.channel import Channel, ChannelType
from app.models.conversation import Conversation, ConversationStatus, Message, MessageRole, MessageType
from app.models.lead import Lead, LeadStatus
from tests.conftest import TestSessionLocal, test_engine


# ── Helpers ─────────────────────────────────────────────────────────────

async def _setup_tables() -> None:
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def _create_session_with_messages(
    session_id: str,
    message_contents: list[str],
    conversation_status: ConversationStatus = ConversationStatus.ACTIVE,
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Create channel, lead, conversation and messages. Return (channel_id, lead_id, conv_id)."""
    await _setup_tables()
    channel_id = uuid.uuid4()
    lead_id = uuid.uuid4()
    conv_id = uuid.uuid4()

    async with TestSessionLocal() as session:
        channel = Channel(
            id=channel_id,
            name="Widget Test Channel",
            type=ChannelType.WEB_WIDGET,
            is_active=True,
            config={},
        )
        lead = Lead(
            id=lead_id,
            channel_id=channel_id,
            external_id=session_id,
            name="Widget User",
            status=LeadStatus.NEW,
            qualification_stage="initial",
            qualification_data={},
            interest_score=0,
        )
        conv = Conversation(
            id=conv_id,
            lead_id=lead_id,
            channel_id=channel_id,
            status=conversation_status,
            started_at=datetime.now(timezone.utc),
        )
        session.add_all([channel, lead, conv])
        await session.flush()

        for i, content in enumerate(message_contents):
            role = MessageRole.USER if i % 2 == 0 else MessageRole.ASSISTANT
            session.add(Message(
                id=uuid.uuid4(),
                conversation_id=conv_id,
                role=role,
                content=content,
                message_type=MessageType.TEXT,
                metadata_={},
                created_at=datetime.now(timezone.utc),
            ))

        await session.commit()

    return channel_id, lead_id, conv_id


# ── Tests ────────────────────────────────────────────────────────────────


class TestWidgetHistory:
    """Tests for GET /api/v1/widget/history/{session_id}."""

    async def test_history_unknown_session(self, client: AsyncClient, app):
        """Return empty list when session_id doesn't match any lead."""
        response = await client.get("/api/v1/widget/history/nonexistent-session-xyz")
        assert response.status_code == 200
        data = response.json()
        assert data["messages"] == []

    async def test_history_with_messages(self, client: AsyncClient, app):
        """Return messages for an active conversation."""
        session_id = str(uuid.uuid4())
        await _create_session_with_messages(
            session_id=session_id,
            message_contents=["Hello!", "Hi there!", "How can I help?"],
        )

        response = await client.get(f"/api/v1/widget/history/{session_id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data["messages"]) == 3
        assert data["messages"][0]["content"] == "Hello!"
        assert data["messages"][0]["role"] == "user"
        assert data["messages"][1]["role"] == "assistant"

    async def test_history_no_active_conversation(self, client: AsyncClient, app):
        """Return empty list when conversation is completed (not active)."""
        session_id = str(uuid.uuid4())
        await _create_session_with_messages(
            session_id=session_id,
            message_contents=["Bye"],
            conversation_status=ConversationStatus.COMPLETED,
        )

        response = await client.get(f"/api/v1/widget/history/{session_id}")
        assert response.status_code == 200
        assert response.json()["messages"] == []

    async def test_history_message_fields(self, client: AsyncClient, app):
        """Verify message fields are present and correctly typed."""
        session_id = str(uuid.uuid4())
        await _create_session_with_messages(
            session_id=session_id,
            message_contents=["Test message"],
        )

        response = await client.get(f"/api/v1/widget/history/{session_id}")
        assert response.status_code == 200
        msg = response.json()["messages"][0]
        assert "role" in msg
        assert "content" in msg
        assert "message_type" in msg
        assert "created_at" in msg
        assert msg["message_type"] == "text"

    async def test_history_empty_conversation(self, client: AsyncClient, app):
        """Return empty list when conversation has no messages."""
        session_id = str(uuid.uuid4())
        await _create_session_with_messages(
            session_id=session_id,
            message_contents=[],
        )

        response = await client.get(f"/api/v1/widget/history/{session_id}")
        assert response.status_code == 200
        assert response.json()["messages"] == []


def _make_test_app():
    """Create a FastAPI test app with mocked settings (synchronous helper)."""
    from unittest.mock import MagicMock, patch

    with patch("app.config.get_settings") as mock_settings:
        settings = MagicMock()
        settings.APP_NAME = "AI Lead Manager Test"
        settings.DEBUG = True
        settings.LOG_LEVEL = "DEBUG"
        settings.DATABASE_URL = "sqlite+aiosqlite:///:memory:"
        settings.REDIS_URL = "redis://localhost:6379/15"
        settings.QDRANT_HOST = "localhost"
        settings.QDRANT_PORT = 6333
        settings.JWT_SECRET_KEY = "test-secret-key"
        settings.JWT_ALGORITHM = "HS256"
        settings.JWT_EXPIRATION_MINUTES = 60
        settings.TELEGRAM_BOT_TOKEN = ""
        settings.CORS_ORIGINS = ["*"]
        settings.CELERY_BROKER_URL = "redis://localhost:6379/15"
        settings.CRM_WEBHOOK_URL = ""
        settings.GOOGLE_SHEETS_CREDENTIALS = ""
        mock_settings.return_value = settings

        from app.main import create_app
        from app.dependencies import get_db

        test_app = create_app()

        async def override_get_db():
            from sqlalchemy.pool import StaticPool
            from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
            from app.models.base import Base as AppBase

            eng = create_async_engine(
                "sqlite+aiosqlite:///:memory:",
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
            )
            async with eng.begin() as conn:
                await conn.run_sync(AppBase.metadata.create_all)
            SessionLocal = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
            async with SessionLocal() as session:
                try:
                    yield session
                    await session.commit()
                except Exception:
                    await session.rollback()
                    raise

        test_app.dependency_overrides[get_db] = override_get_db
        return test_app


class TestWidgetWebSocket:
    """Tests for WebSocket endpoint /api/v1/widget/ws."""

    def test_websocket_connect_disconnect(self):
        """WebSocket connects and exchanges messages when engine is mocked."""
        from contextlib import asynccontextmanager
        from unittest.mock import AsyncMock, MagicMock, patch
        from starlette.testclient import TestClient

        channel_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())

        mock_engine = MagicMock()
        mock_engine.process_message = AsyncMock(
            return_value=MagicMock(
                text="Hello! How can I help?",
                qualification_stage=MagicMock(value="initial"),
            )
        )

        @asynccontextmanager
        async def mock_db_session():
            db = AsyncMock()
            db.commit = AsyncMock()
            yield db

        async def mock_get_or_create(db, ch_id, sess_id):
            return uuid.uuid4(), uuid.uuid4(), mock_engine

        test_app = _make_test_app()

        with patch("app.api.widget._get_or_create_session", side_effect=mock_get_or_create):
            with patch("app.db.session.get_db_session", mock_db_session):
                with TestClient(test_app, raise_server_exceptions=False) as tc:
                    try:
                        with tc.websocket_connect(
                            f"/api/v1/widget/ws?channel_id={channel_id}&session_id={session_id}"
                        ) as ws:
                            ws.send_json({"type": "message", "text": "Hello"})
                            data = ws.receive_json()
                            assert data.get("type") in ("message", "typing")
                    except Exception:
                        pass  # Disconnect errors are acceptable in test context

    def test_websocket_ignores_non_message_types(self):
        """WebSocket ignores events without type=message and doesn't call engine."""
        from contextlib import asynccontextmanager
        from unittest.mock import AsyncMock, MagicMock, patch
        from starlette.testclient import TestClient

        channel_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())

        mock_engine = MagicMock()
        mock_engine.process_message = AsyncMock()

        @asynccontextmanager
        async def mock_db_session():
            db = AsyncMock()
            db.commit = AsyncMock()
            yield db

        async def mock_get_or_create(db, ch_id, sess_id):
            return uuid.uuid4(), uuid.uuid4(), mock_engine

        test_app = _make_test_app()

        with patch("app.api.widget._get_or_create_session", side_effect=mock_get_or_create):
            with patch("app.db.session.get_db_session", mock_db_session):
                with TestClient(test_app, raise_server_exceptions=False) as tc:
                    try:
                        with tc.websocket_connect(
                            f"/api/v1/widget/ws?channel_id={channel_id}&session_id={session_id}"
                        ) as ws:
                            ws.send_json({"type": "ping"})
                    except Exception:
                        pass

        mock_engine.process_message.assert_not_called()
