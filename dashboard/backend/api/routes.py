from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import json
from datetime import datetime
from pathlib import Path

from dashboard.backend.models import ServiceStatus, SnapshotInfo
from dashboard.backend.services.systemd import (
    check_systemd_service,
    check_docker_containers,
    tail_systemd_logs,
    run_systemctl_command,
    run_security_audit,
    validate_all_configs,
)
from dashboard.backend.services.state_manager import StateManager

router = APIRouter(prefix="/api/v1", tags=["dashboard"])


class SnapshotCreateRequest(BaseModel):
    name: Optional[str] = None


class CreateSnapshotResponse(BaseModel):
    snapshot: str
    path: str
    timestamp: str


class RestoreSnapshotResponse(BaseModel):
    status: str
    restored_configs: List[str]
    restored_services: List[str]
    errors: List[str]


@router.get("/services", response_model=List[ServiceStatus])
async def get_services():
    services = []
    for svc in ["hermes-gateway", "open-design", "openclaw-gateway"]:
        status = await check_systemd_service(svc)
        services.append(status)
    docker_services = await check_docker_containers()
    services.extend(docker_services)
    return services


@router.get("/logs/{service}")
async def stream_logs(service: str, lines: int = 100):
    logs = await tail_systemd_logs(service, lines)
    return {"service": service, "logs": logs}


@router.post("/services/{service}/restart")
async def restart_service(service: str):
    result = await run_systemctl_command(service, "restart")
    if result["returncode"] != 0:
        raise HTTPException(status_code=500, detail=result["stderr"])
    return {"service": service, "action": "restart", "result": "ok"}


@router.post("/services/{service}/start")
async def start_service(service: str):
    result = await run_systemctl_command(service, "start")
    if result["returncode"] != 0:
        raise HTTPException(status_code=500, detail=result["stderr"])
    return {"service": service, "action": "start", "result": "ok"}


@router.post("/services/{service}/stop")
async def stop_service(service: str):
    result = await run_systemctl_command(service, "stop")
    if result["returncode"] != 0:
        raise HTTPException(status_code=500, detail=result["stderr"])
    return {"service": service, "action": "stop", "result": "ok"}


@router.get("/snapshots", response_model=List[SnapshotInfo])
async def list_snapshots():
    sm = StateManager(Path.home() / ".hermes")
    snaps = sm.list_snapshots()
    result = []
    for s in snaps:
        path = Path(s["file"])
        size = path.stat().st_size if path.exists() else 0
        result.append(SnapshotInfo(name=s["name"], timestamp=s["timestamp"], size=size))
    return result


@router.post("/snapshots", response_model=CreateSnapshotResponse)
async def create_snapshot(body: SnapshotCreateRequest = Body(default=SnapshotCreateRequest())):
    """Create a system state snapshot.

    Request body (JSON):
        {"name": "optional-snapshot-name"}
    or empty body for auto-generated name.
    """
    sm = StateManager(Path.home() / ".hermes")
    snapshot = sm.capture_snapshot(body.name)
    path = sm.save_snapshot(snapshot)
    return CreateSnapshotResponse(
        snapshot=snapshot["metadata"]["name"],
        path=str(path),
        timestamp=snapshot["metadata"]["timestamp"],
    )


@router.post("/snapshots/{snapshot_name}/restore", response_model=RestoreSnapshotResponse)
async def restore_snapshot(snapshot_name: str):
    """
    Restore system state from a snapshot by name (without .json extension).

    The snapshot file is looked up by pattern in the snapshots directory.
    """
    sm = StateManager(Path.home() / ".hermes")
    snaps = sm.list_snapshots()

    # Find snapshot by name (exact match first, then prefix match)
    snapshot_path = None
    for s in snaps:
        if s["name"] == snapshot_name or s["name"].startswith(snapshot_name):
            snapshot_path = Path(s["file"])
            break

    if snapshot_path is None or not snapshot_path.exists():
        raise HTTPException(status_code=404, detail=f"Snapshot '{snapshot_name}' not found")

    snapshot = sm.load_snapshot(snapshot_path)
    if snapshot is None:
        raise HTTPException(status_code=500, detail="Failed to load snapshot file")

    results = sm.apply_snapshot(snapshot)

    success = len(results["errors"]) == 0
    return RestoreSnapshotResponse(
        status="ok" if success else "partial",
        restored_configs=results["restored_configs"],
        restored_services=results["restored_services"],
        errors=results["errors"],
    )


@router.get("/security/status")
async def security_status():
    checks = await run_security_audit()
    overall = "pass" if all(c["pass"] for c in checks) else "fail"
    return {"checks": checks, "overall": overall}


@router.post("/config/validate")
async def validate_configs():
    results = await validate_all_configs()
    valid = all(r["valid"] for r in results)
    return {"valid": valid, "details": results}