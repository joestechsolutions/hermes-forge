from fastapi import APIRouter, HTTPException, Body, Query
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dashboard.backend.models import ServiceStatus, SnapshotInfo
from dashboard.backend.services.systemd import (
    check_systemd_service,
    check_docker_containers,
    managed_service_names,
    tail_systemd_logs,
    tail_docker_logs,
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
    names = await managed_service_names()
    services = await asyncio.gather(*(check_systemd_service(name) for name in names))
    docker_services = await check_docker_containers()
    services.extend(docker_services)
    return services


async def _known_unit(service: str) -> str:
    name = service.removesuffix(".service")
    if name not in await managed_service_names():
        raise HTTPException(status_code=404, detail="Unknown managed service")
    return name


@router.get("/logs/{service}")
async def stream_logs(service: str, lines: int = Query(100, ge=1, le=500)):
    if service.removesuffix(".service") in await managed_service_names():
        logs = await tail_systemd_logs(service, lines)
    else:
        containers = await check_docker_containers()
        if service not in {c["name"] for c in containers}:
            raise HTTPException(status_code=404, detail="Unknown service")
        logs = await tail_docker_logs(service, lines)
    return {"service": service, "logs": logs}


@router.post("/services/{service}/restart")
async def restart_service(service: str):
    service = await _known_unit(service)
    result = await run_systemctl_command(service, "restart")
    if result["returncode"] != 0:
        raise HTTPException(status_code=500, detail=result["stderr"])
    return {"service": service, "action": "restart", "result": "ok"}


@router.post("/services/{service}/start")
async def start_service(service: str):
    service = await _known_unit(service)
    result = await run_systemctl_command(service, "start")
    if result["returncode"] != 0:
        raise HTTPException(status_code=500, detail=result["stderr"])
    return {"service": service, "action": "start", "result": "ok"}


@router.post("/services/{service}/stop")
async def stop_service(service: str):
    service = await _known_unit(service)
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
    return {"checks": checks, "overall": overall, "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}


@router.post("/config/validate")
async def validate_configs():
    results = await validate_all_configs()
    valid = all(r["valid"] for r in results)
    return {"valid": valid, "details": results}

# ── Command Center (cron reports / briefings) ──────────────────────────────
from dashboard.backend.services import command_center, agent_roster, live_config, agent_activity, workflow
from dashboard.backend.services.agent_status import check_all_agents


@router.get("/agents/status")
async def agents_status():
    return await asyncio.to_thread(check_all_agents)


@router.get("/models/providers")
async def models_providers():
    from dashboard.backend.services.model_providers import check_all_providers
    return await check_all_providers()


@router.get("/command-center/summary")
async def command_center_summary():
    return command_center.summary()


@router.get("/command-center/categories")
async def command_center_categories():
    return command_center.categories()


@router.get("/command-center/jobs")
async def command_center_jobs(category: Optional[str] = None, outputs: bool = False):
    return command_center.list_jobs(category=category, include_outputs=outputs)


@router.get("/command-center/reports")
async def command_center_reports(limit: int = 12):
    return command_center.recent_reports(limit)


@router.get("/command-center/report/{job_id}")
async def command_center_report(job_id: str, filename: Optional[str] = None):
    text = command_center.report_text(job_id, filename)
    if text is None:
        raise HTTPException(status_code=404, detail="report not found")
    return {"job_id": job_id, "file": filename, "content": text}


@router.get("/live/overview")
async def live_overview():
    """One read-only live view for the agent, model, and provider panels."""
    return await live_config.overview()


@router.get("/models")
async def models_list():
    """Current model configuration and scheduled-job pins, not a static registry."""
    return live_config.model_snapshot()


@router.get("/workflow")
async def workflow_status():
    """Sanitized lead/delegation/advisor activity from the Hermes ledger."""
    home = Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))).expanduser()
    return await asyncio.to_thread(workflow.read_workflow, home)


@router.get("/agents")
async def agents_roster():
    """Read-only profile metadata and work status; no prompts or credentials."""
    return await asyncio.to_thread(agent_roster.roster)


@router.get("/agents/{profile_id}")
async def agent_activity_detail(profile_id: str):
    """Session metadata, owned jobs, and bounded outputs for one agent."""
    try:
        return await asyncio.to_thread(agent_activity.agent_detail, profile_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Agent not found")
