from datetime import datetime
from typing import Dict, Any, Optional
from pydantic import BaseModel

class ServiceStatus(BaseModel):
    name: str
    state: str
    port: Optional[int] = None
    uptime: Optional[str] = None
    last_log: Optional[str] = None

class SystemMetrics(BaseModel):
    cpu_percent: float
    memory: Dict[str, Any]
    disk: Dict[str, Any]
    gpu: Optional[Dict[str, Any]] = None
    timestamp: datetime

class SnapshotInfo(BaseModel):
    name: str
    timestamp: str
    size: int
