"""
WebSocket Streaming Endpoint for SYNQ.
Streams real-time agent execution events, token generation, and state transitions to the frontend.
"""

import asyncio
import json
import logging
from typing import Dict, Set

from config import get_settings
from core.coordinator import coordinator
from core.security import decode_access_token, hash_api_key
from db.models import Project, User, UserRole
from db.session import AsyncSessionLocal
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(tags=["websockets"])


class ConnectionManager:
    """Manages active WebSocket connections grouped by project_id."""

    def __init__(self):
        # project_id -> set of active WebSockets
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # Hook into task coordinator
        coordinator.add_event_listener(self.broadcast_event)

    async def connect(self, websocket: WebSocket, project_id: str):
        await websocket.accept()
        if project_id not in self.active_connections:
            self.active_connections[project_id] = set()
        self.active_connections[project_id].add(websocket)
        logger.info("Client connected to project WebSocket %s (total: %d)", project_id, len(self.active_connections[project_id]))

    def disconnect(self, websocket: WebSocket, project_id: str):
        if project_id in self.active_connections:
            self.active_connections[project_id].discard(websocket)
            if not self.active_connections[project_id]:
                del self.active_connections[project_id]
        logger.info("Client disconnected from project WebSocket %s", project_id)

    async def broadcast_event(self, project_id: str, event_data: dict):
        """Called by coordinator when an execution event happens."""
        connections = self.active_connections.get(project_id, set()).copy()
        if not connections:
            return

        message = json.dumps(event_data)
        dead_connections = set()

        for conn in connections:
            try:
                await conn.send_text(message)
            except Exception as exc:
                logger.debug("Failed to send message to websocket client: %s", exc)
                dead_connections.add(conn)

        for dead in dead_connections:
            self.disconnect(dead, project_id)


manager = ConnectionManager()


@router.websocket("/ws/{project_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    project_id: str,
    token: Optional[str] = Query(None),
    api_key: Optional[str] = Query(None),
):
    # Enforce WebSocket authentication when auth is enabled
    if settings.auth_enabled:
        # Check query param, then fallback to Authorization / X-API-Key headers
        auth_token = token
        auth_api_key = api_key
        if not auth_token:
            auth_header = websocket.headers.get("authorization", "")
            if auth_header.lower().startswith("bearer "):
                auth_token = auth_header.split(" ", 1)[1].strip()
        if not auth_api_key:
            auth_api_key = websocket.headers.get("x-api-key")

        authenticated_user = None
        async with AsyncSessionLocal() as db:
            if auth_token:
                payload = decode_access_token(auth_token)
                if payload and "sub" in payload:
                    authenticated_user = await db.get(User, payload["sub"])
            elif auth_api_key:
                key_hash = hash_api_key(auth_api_key)
                res = await db.execute(select(User).where(User.api_key_hash == key_hash))
                authenticated_user = res.scalar_one_or_none()

            if not authenticated_user or not authenticated_user.is_active:
                logger.warning("Rejected unauthenticated WebSocket connection for project %s", project_id)
                await websocket.close(code=1008, reason="Authentication failed: invalid or expired credentials.")
                return

            # Check project ownership / permissions
            project = await db.get(Project, project_id)
            if project and authenticated_user.role != UserRole.ADMIN.value:
                if project.owner_id and project.owner_id != authenticated_user.id:
                    logger.warning("Forbidden WebSocket access: user %s attempted to access project %s", authenticated_user.id, project_id)
                    await websocket.close(code=1008, reason="Forbidden: Access to this project stream is denied.")
                    return

    await manager.connect(websocket, project_id)
    # Send initial greeting
    await websocket.send_json({
        "project_id": project_id,
        "event_type": "connected",
        "data": {"message": f"Connected to live stream for project {project_id}"},
    })
    try:
        while True:
            # Keep socket open and receive any ping/commands from client
            data = await websocket.receive_text()
            # If client sends ping, respond with pong
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_json({"event_type": "pong"})
            except Exception:
                pass
    except WebSocketDisconnect:
        manager.disconnect(websocket, project_id)
    except Exception as exc:
        logger.warning("WebSocket error for project %s: %s", project_id, exc)
        manager.disconnect(websocket, project_id)
