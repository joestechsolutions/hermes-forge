import sys, os

# Ensure project root is on path (works regardless of env)
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

import psutil
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder
from websockets.exceptions import ConnectionClosed

from dashboard.backend.models import ServiceStatus, SystemMetrics, SnapshotInfo
from dashboard.backend.services import systemd as systemd_services
from dashboard.backend.api.routes import router as api_router
from dashboard.backend.services.auth_routes import auth_router, AuthGateMiddleware

app = FastAPI(title="Hermes Infrastructure Dashboard", version="2.0.0")

# ── Magic-link auth gate (public tunnel protection) ─────────────────────────
# Order matters: middleware wraps everything below it.
app.add_middleware(AuthGateMiddleware)
app.include_router(auth_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8643", "http://localhost:8643"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                # Client disconnected mid-send; remove stale connection
                try:
                    self.active_connections.remove(connection)
                except ValueError:
                    pass  # already removed

manager = ConnectionManager()

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

@app.get("/api/v1/system/metrics")
async def system_metrics_rest():
    """REST fallback for metrics when WebSocket passthrough is unavailable (e.g. tunnels)."""
    return await asyncio.to_thread(collect_system_metrics)

@app.websocket("/ws/metrics")
async def websocket_metrics(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            metrics = await asyncio.to_thread(collect_system_metrics)
            await websocket.send_json(jsonable_encoder(metrics))
            await asyncio.sleep(2)
    except (WebSocketDisconnect, ConnectionClosed):
        pass
    finally:
        manager.disconnect(websocket)

def collect_system_metrics() -> SystemMetrics:
    cpu = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    gpu = None
    try:
        import subprocess
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=utilization.gpu,memory.used,memory.total', '--format=csv,noheader,nounits'],
            capture_output=True, text=True, timeout=1
        )
        if result.returncode == 0:
            vals = result.stdout.strip().split(', ')
            gpu = {
                "utilization": float(vals[0]),
                "memory_used": float(vals[1]),
                "memory_total": float(vals[2])
            }
    except Exception:
        pass
    return SystemMetrics(
        cpu_percent=cpu,
        memory={
            "total": memory.total,
            "available": memory.available,
            "used": memory.used,
            "free": memory.free,
            "percent": memory.percent
        },
        disk={
            "total": disk.total,
            "used": disk.used,
            "free": disk.free,
            "percent": disk.percent
        },
        gpu=gpu,
        timestamp=datetime.utcnow()
    )

# Static file serving for the React SPA. Tests/preview can select an isolated build.
frontend_dist = os.environ.get("DASHBOARD_FRONTEND_DIST", "/home/lurkr/ai-platform/dashboard/frontend/dist")
if os.path.isdir(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8643)
