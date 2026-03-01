"""Widget API endpoints -- WebSocket and REST for the chat widget.

WebSocket endpoint for real-time communication, REST endpoints as fallback.
Handles session initialization, message processing, and history retrieval.
"""

import structlog
import uuid

from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.context_builder import ContextBuilder
from app.ai.embeddings import EmbeddingsManager
from app.ai.engine import ConversationEngine
from app.ai.rag import RAGPipeline
from app.ai.tools import ToolHandler
from app.api.ws_manager import manager as connection_manager
from app.channels.web_widget import WebWidgetAdapter
from app.config import get_settings
from app.dependencies import get_db
from app.models.conversation import ConversationStatus, MessageRole
from app.models.conversation import Conversation as ConversationModel
from app.rate_limit import limiter
from app.services.conversation_service import ConversationService
from app.services.lead_service import LeadService

logger = structlog.get_logger(__name__)

router = APIRouter()

settings = get_settings()


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class WidgetInitRequest(BaseModel):
    """Request to initialize a widget session."""

    channel_id: str = Field(..., description="Channel UUID")


class WidgetInitResponse(BaseModel):
    """Response with session info and greeting."""

    session_id: str
    greeting: str


class WidgetMessageRequest(BaseModel):
    """Request to send a message via REST fallback."""

    channel_id: str
    session_id: str
    text: str = Field(..., min_length=1)


class WidgetMessageResponse(BaseModel):
    """Response from AI engine via REST."""

    text: str
    qualification_stage: str | None = None


class WidgetHistoryMessage(BaseModel):
    """Single message in the conversation history."""

    role: str
    content: str
    message_type: str
    created_at: str


class WidgetHistoryResponse(BaseModel):
    """Response with conversation history."""

    messages: list[WidgetHistoryMessage]


# ---------------------------------------------------------------------------
# Helpers -- build the engine from a DB session
# ---------------------------------------------------------------------------


async def _build_engine(db: AsyncSession) -> ConversationEngine:
    """Create a ConversationEngine with all its dependencies.

    Called per-request to ensure each request gets its own DB session.
    The engine uses db_session to create per-owner LLM clients dynamically
    based on channel.owner_id, determined during context building.
    """
    from qdrant_client import AsyncQdrantClient

    embeddings = EmbeddingsManager.get_instance()
    qdrant = AsyncQdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
    rag = RAGPipeline(qdrant_client=qdrant, embeddings_manager=embeddings)
    context_builder = ContextBuilder(db_session=db, rag_pipeline=rag)
    tool_handler = ToolHandler()
    conversation_service = ConversationService(db_session=db)
    lead_service = LeadService(db_session=db)

    return ConversationEngine(
        llm_client=None,
        context_builder=context_builder,
        tool_handler=tool_handler,
        conversation_service=conversation_service,
        lead_service=lead_service,
        db_session=db,
    )


async def _get_or_create_session(
    db: AsyncSession,
    channel_id_str: str,
    session_id: str,
) -> tuple[uuid.UUID, uuid.UUID, ConversationEngine]:
    """Resolve or create lead + conversation for a widget session.

    Returns:
        Tuple of (lead_id, conversation_id, engine).
    """
    channel_id = uuid.UUID(channel_id_str)
    lead_service = LeadService(db_session=db)
    conversation_service = ConversationService(db_session=db)

    lead = await lead_service.get_or_create_lead(
        channel_id=channel_id,
        external_id=session_id,
    )

    conversation = await conversation_service.get_or_create_conversation(
        lead_id=lead.id,
        channel_id=channel_id,
    )

    engine = await _build_engine(db)

    return lead.id, conversation.id, engine


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------


@router.websocket("/ws")
async def widget_websocket(
    websocket: WebSocket,
    channel_id: str,
    session_id: str,
):
    """WebSocket endpoint for the chat widget.

    Query params:
        channel_id: UUID of the widget channel.
        session_id: UUID of the client session.

    Message format (incoming):
        {"type": "message", "text": "...", "session_id": "..."}

    Message format (outgoing):
        {"type": "message" | "typing", "text": "...", "timestamp": "..."}
    """
    # Connect
    await connection_manager.connect(session_id, websocket)

    # Get DB session manually (WebSocket endpoints don't support Depends in the same way)
    from app.db.session import get_db_session

    try:
        async with get_db_session() as db:
            lead_id, conversation_id, engine = await _get_or_create_session(
                db, channel_id, session_id,
            )

            # Create the widget adapter for sending responses
            adapter = WebWidgetAdapter(connection_manager)

            # Message loop
            while True:
                try:
                    raw = await websocket.receive_json()
                except WebSocketDisconnect:
                    break

                msg_type = raw.get("type", "")
                text = raw.get("text", "").strip()

                if msg_type != "message" or not text:
                    continue

                # AI gate: check conversation status (may change mid-session)
                conversation_service = ConversationService(db_session=db)
                conv = await conversation_service.get_conversation(conversation_id)
                if conv and conv.status == ConversationStatus.HANDED_OFF:
                    await conversation_service.add_message(
                        conversation_id=conversation_id,
                        role=MessageRole.USER,
                        content=text,
                    )
                    await adapter.send_message(
                        external_id=session_id,
                        text="Ваш вопрос принят, менеджер ответит в ближайшее время.",
                    )
                    continue

                # Send typing indicator
                await adapter.send_typing(session_id)

                try:
                    # Process through AI engine
                    response = await engine.process_message(
                        conversation_id=conversation_id,
                        user_message=text,
                    )

                    # Send response
                    await adapter.send_message(
                        external_id=session_id,
                        text=response.text,
                    )

                except Exception:
                    logger.exception("Error processing widget message: session=%s", session_id)
                    await adapter.send_message(
                        external_id=session_id,
                        text="Извините, произошла ошибка. Попробуйте ещё раз.",
                    )

            # Commit any DB changes from the session
            await db.commit()

    except Exception:
        logger.exception("WebSocket session error: session=%s", session_id)
    finally:
        await connection_manager.disconnect(session_id)


# ---------------------------------------------------------------------------
# REST fallback endpoints
# ---------------------------------------------------------------------------


@router.post("/init", response_model=WidgetInitResponse)
@limiter.limit("30/minute")
async def widget_init(
    request: Request,
    body: WidgetInitRequest,
    db: AsyncSession = Depends(get_db),
):
    """Initialize a widget chat session.

    Creates a lead and conversation, returns a session_id and greeting.
    """
    session_id = str(uuid.uuid4())

    lead_id, conversation_id, engine = await _get_or_create_session(
        db, body.channel_id, session_id,
    )

    # Start conversation with greeting
    _, greeting = await engine.start_conversation(
        lead_id=lead_id,
        channel_id=uuid.UUID(body.channel_id),
    )

    return WidgetInitResponse(session_id=session_id, greeting=greeting)


@router.post("/messages", response_model=WidgetMessageResponse)
@limiter.limit("30/minute")
async def widget_send_message(
    request: Request,
    body: WidgetMessageRequest,
    db: AsyncSession = Depends(get_db),
):
    """Send a message via REST (fallback when WebSocket is down).

    Processes the message through the AI engine and returns the response.
    """
    _, conversation_id, engine = await _get_or_create_session(
        db, body.channel_id, body.session_id,
    )

    # AI gate: check conversation status
    conversation_service = ConversationService(db_session=db)
    conv = await conversation_service.get_conversation(conversation_id)
    if conv and conv.status == ConversationStatus.HANDED_OFF:
        await conversation_service.add_message(
            conversation_id=conversation_id,
            role=MessageRole.USER,
            content=body.text,
        )
        return WidgetMessageResponse(
            text="Ваш вопрос принят, менеджер ответит в ближайшее время.",
            qualification_stage=None,
        )

    response = await engine.process_message(
        conversation_id=conversation_id,
        user_message=body.text,
    )

    return WidgetMessageResponse(
        text=response.text,
        qualification_stage=response.qualification_stage.value,
    )


@router.get("/history/{session_id}", response_model=WidgetHistoryResponse)
async def widget_history(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get the conversation history for a widget session.

    Looks up the lead by session_id (external_id) and returns messages
    from the most recent active conversation.
    """
    from sqlalchemy import select

    from app.models.conversation import Conversation, Message
    from app.models.lead import Lead

    # Find lead by external_id (session_id)
    result = await db.execute(
        select(Lead).where(Lead.external_id == session_id)
    )
    lead = result.scalar_one_or_none()

    if not lead:
        return WidgetHistoryResponse(messages=[])

    # Find active or handed-off conversation
    result = await db.execute(
        select(Conversation).where(
            Conversation.lead_id == lead.id,
            Conversation.status.in_([ConversationStatus.ACTIVE, ConversationStatus.HANDED_OFF]),
        )
    )
    conversation = result.scalar_one_or_none()

    if not conversation:
        return WidgetHistoryResponse(messages=[])

    # Get messages
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.asc())
        .limit(100)
    )
    messages = result.scalars().all()

    return WidgetHistoryResponse(
        messages=[
            WidgetHistoryMessage(
                role=msg.role.value,
                content=msg.content,
                message_type=msg.message_type.value if msg.message_type else "text",
                created_at=msg.created_at.isoformat() if msg.created_at else "",
            )
            for msg in messages
        ]
    )
