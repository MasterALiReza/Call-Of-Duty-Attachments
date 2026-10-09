import asyncio
import json
import psutil
import time
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from core.database.database_adapter import get_database_adapter

router = APIRouter(tags=["Real-time WebSockets"])


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in list(self.active_connections):
            try:
                await connection.send_text(json.dumps(message))
            except Exception:
                self.disconnect(connection)


manager = ConnectionManager()


@router.websocket("/ws/live")
async def websocket_live_stream(websocket: WebSocket):
    """Real-time server health and stats push to web panel clients"""
    await manager.connect(websocket)
    try:
        while True:
            # Poll server stats every 3 seconds
            cpu = psutil.cpu_percent()
            mem = psutil.virtual_memory().percent
            
            payload = {
                "type": "health_tick",
                "timestamp": time.time(),
                "cpu": cpu,
                "memory": mem,
            }
            await websocket.send_text(json.dumps(payload))
            await asyncio.sleep(3.0)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
