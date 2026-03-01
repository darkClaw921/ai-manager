"""WebSocket connection manager for the chat widget.

Manages active WebSocket connections, provides send/disconnect operations,
and automatically cleans up stale connections.

In production this can be replaced with Redis pub/sub for multi-instance support.
"""

import structlog
from typing import Any

from fastapi import WebSocket
from starlette.websockets import WebSocketState

logger = structlog.get_logger(__name__)


class ConnectionManager:
    """Manages active WebSocket connections keyed by session_id.

    Thread-safe within a single asyncio event loop (no locks needed).
    """

    def __init__(self) -> None:
        # session_id -> WebSocket
        self._connections: dict[str, WebSocket] = {}

    async def connect(self, session_id: str, websocket: WebSocket) -> None:
        """Accept a WebSocket connection and register it.

        If there is an existing connection for the same session_id (e.g., reconnect),
        the old connection is silently replaced.

        Args:
            session_id: Unique session identifier.
            websocket: The FastAPI/Starlette WebSocket instance.
        """
        await websocket.accept()

        # Close old connection if exists (reconnect scenario)
        old_ws = self._connections.get(session_id)
        if old_ws is not None:
            try:
                await old_ws.close(code=1000, reason="Replaced by new connection")
            except Exception:
                pass
            logger.debug("Replaced existing connection for session %s", session_id)

        self._connections[session_id] = websocket
        logger.info("WebSocket connected: session=%s (total=%d)", session_id, len(self._connections))

    async def disconnect(self, session_id: str) -> None:
        """Remove a connection from the registry.

        Args:
            session_id: Session to disconnect.
        """
        ws = self._connections.pop(session_id, None)
        if ws is not None:
            logger.info("WebSocket disconnected: session=%s (total=%d)", session_id, len(self._connections))

    async def send_message(self, session_id: str, data: dict[str, Any]) -> bool:
        """Send a JSON message to a connected session.

        Args:
            session_id: Target session.
            data: JSON-serializable dict to send.

        Returns:
            True if the message was sent, False if the connection is gone.
        """
        ws = self._connections.get(session_id)
        if ws is None:
            return False

        try:
            await ws.send_json(data)
            return True
        except Exception:
            # Connection is broken -- remove it
            logger.warning("Failed to send to session %s, removing connection", session_id)
            self._connections.pop(session_id, None)
            return False

    async def send_typing(self, session_id: str) -> bool:
        """Send a typing indicator to a session.

        Args:
            session_id: Target session.

        Returns:
            True if sent successfully.
        """
        return await self.send_message(session_id, {"type": "typing"})

    def is_connected(self, session_id: str) -> bool:
        """Check if a session has an active WebSocket connection.

        Args:
            session_id: Session to check.

        Returns:
            True if the session is currently connected.
        """
        ws = self._connections.get(session_id)
        if ws is None:
            return False
        # Also check the underlying WebSocket state
        if ws.client_state != WebSocketState.CONNECTED:
            self._connections.pop(session_id, None)
            return False
        return True

    @property
    def active_count(self) -> int:
        """Number of currently active connections."""
        return len(self._connections)


# Singleton instance used across the application
manager = ConnectionManager()
