"""Detailed, read-only activity for one installed agent profile."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

from dashboard.backend.services import agent_roster, command_center
from dashboard.backend.services.agent_sessions import read_sessions


def _job_view(job: dict[str, Any]) -> dict[str, Any]:
    latest = command_center._latest_output(str(job.get("id") or ""))
    if latest:
        latest = {
            "file": latest["file"],
            "mtime": latest["mtime"],
            "body": latest["body"][:5000],
        }
    schedule = cast(dict[str, Any], job.get("schedule")) if isinstance(job.get("schedule"), dict) else {}
    return {
        "id": str(job.get("id") or job.get("name") or ""),
        "name": str(job.get("name") or "Scheduled job"),
        "skill": job.get("skill") if isinstance(job.get("skill"), str) else None,
        "model": job.get("model") if isinstance(job.get("model"), str) else None,
        "enabled": bool(job.get("enabled", True)) and job.get("state") not in ("paused", "completed"),
        "state": job.get("state"),
        "cadence": command_center._cadence(schedule),
        "last_status": job.get("last_status"),
        "last_run_at": job.get("last_run_at"),
        "next_run_at": job.get("next_run_at"),
        "failure_streak": max(0, int(job.get("failure_streak") or 0)),
        "paused_reason": job.get("paused_reason") if isinstance(job.get("paused_reason"), str) else None,
        "latest_output": latest,
    }


def agent_detail(profile_id: str, home: Path | None = None) -> dict[str, Any]:
    home = home or Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))).expanduser()
    profiles = home / "profiles" if (home / "profiles").is_dir() else home
    profile = profiles / profile_id
    if not profile.is_dir() or not (profile / "profile.yaml").is_file():
        raise KeyError(profile_id)
    cards = agent_roster.roster(home)["agents"]
    card = next((agent for agent in cards if agent["id"] == profile_id), None)
    if card is None:
        raise KeyError(profile_id)
    shared = agent_roster._shared_jobs(home)
    jobs = agent_roster.owned_jobs(profile_id, profile, shared)
    jobs.sort(key=lambda job: agent_roster._timestamp(job.get("last_run_at")), reverse=True)
    activity = read_sessions(profile, limit=6)
    return {
        "agent": card,
        "active_now": activity["active_now"],
        "current_title": activity["current_title"],
        "activity_available": activity["available"],
        "sessions": activity["sessions"],
        "jobs": [_job_view(job) for job in jobs[:20]],
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
