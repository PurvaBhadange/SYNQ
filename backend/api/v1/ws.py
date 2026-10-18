"""
WebSocket Streaming Endpoint for SYNQ.
Streams real-time agent execution events, token generation, and state transitions to the frontend.
"""

import asyncio
import json
import logging
from typing import Dict, Set

from core.coordinator import coordinator
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

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
async def websocket_endpoint(websocket: WebSocket, project_id: str):
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
