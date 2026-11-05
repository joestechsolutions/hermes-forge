"""Read-only roster of installed Hermes bot profiles and observed activity."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from dashboard.backend.services.agent_sessions import read_sessions

BOT_ORDER = (
    "atlaschiefofstaff", "kairovpengineering", "sentryvpinfrastructure",
    "sterlingcfo", "novacmo", "ledger", "sparrow",
)
ROLES = {
    "atlaschiefofstaff": ("Atlas", "Chief of Staff", ("cos_",)),
    "kairovpengineering": ("Kairo", "VP Engineering", ("vp_engineering",)),
    "sentryvpinfrastructure": ("Sentry", "VP Infrastructure", ("vp_infrastructure",)),
    "sterlingcfo": ("Sterling", "CFO", ("cfo_", "jts_cfo_")),
    "novacmo": ("Nova", "CMO", ("cmo_",)),
    "ledger": ("Ledger", "RenFaire Revenue Analyst", ()),
    "sparrow": ("Sparrow", "Research Assistant", ()),
}
JOB_SKILL_OWNERS = {
    "jts-cfo": "sterlingcfo",
    "joe-content-lane": "novacmo",
    "renfaire-content-lane": "novacmo",
    "renfaire-directory-site": "kairovpengineering",
}
JOB_NAME_OWNERS = {
    "renfaire_affiliate_watch": "ledger",
}


def _profile_meta(profile: Path) -> tuple[str, str, str]:
    fallback_name, role, _ = ROLES.get(
        profile.name, (profile.name.replace("_", " ").title(), "Hermes Agent", ())
    )
    description = "Installed Hermes agent"
    try:
        data = yaml.safe_load((profile / "profile.yaml").read_text()) or {}
        if isinstance(data, dict):
            name = data.get("display_name")
            if isinstance(name, str) and name.strip():
                fallback_name = name if profile.name not in ROLES else fallback_name
            value = data.get("description")
            if isinstance(value, str) and value.strip():
                description = " ".join(value.split())[:300]
    except (OSError, ValueError, TypeError, yaml.YAMLError):
        pass
    return fallback_name, role, description


def _profile_jobs(profile: Path) -> list[dict[str, Any]]:
    for path in (profile / "cron/jobs.json", profile / "cron.json", profile / ".cron/jobs.json"):
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError, TypeError):
            continue
        values = data if isinstance(data, list) else data.get("jobs", []) if isinstance(data, dict) else []
        if isinstance(values, list):
            return [j for j in values if isinstance(j, dict)]
    return []


def owned_jobs(key: str, profile: Path, shared: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attribute jobs without exposing prompts or duplicating profile-owned jobs."""
    owned: dict[str, dict[str, Any]] = {
        str(j.get("id") or j.get("name")): j for j in _profile_jobs(profile)
    }
    prefixes = ROLES.get(key, (key, "Hermes Agent", ()))[2]
    for job in shared:
        job_name = str(job.get("name", ""))
        owner = job.get("profile") or JOB_NAME_OWNERS.get(job_name) or JOB_SKILL_OWNERS.get(str(job.get("skill") or ""))
        if not owner and prefixes and job_name.lower().startswith(prefixes):
            owner = key
        if owner == key:
            owned[str(job.get("id") or job_name)] = job
    return list(owned.values())


def _latest_work(profile: Path) -> dict[str, Any]:
    candidates = sorted(profile.joinpath("journal").glob("????-??-??.md"), reverse=True)
    if not candidates:
        return {"last_work_at": None, "summary": None}
    summary = "Latest work journal"
    try:
        for line in candidates[0].read_text(errors="replace").splitlines():
            if line.startswith("## ") and line[3:].strip():
                summary = line[3:].strip()[:160]
                break
    except OSError:
        summary = "Latest work journal — unreadable"
    try:
        modified = datetime.fromtimestamp(candidates[0].stat().st_mtime, timezone.utc).isoformat(timespec="seconds")
    except OSError:
        modified = None
    return {"last_work_at": modified, "summary": summary}


def _timestamp(value: Any) -> float:
    if not isinstance(value, str):
        return 0
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    except (ValueError, OverflowError, OSError):
        return 0


def _latest(values: list[str | None]) -> str | None:
    present = [value for value in values if isinstance(value, str)]
    return max(present, key=_timestamp, default=None)


def _shared_jobs(home: Path) -> list[dict[str, Any]]:
    try:
        data = json.loads((home / "cron/jobs.json").read_text())
        values = data if isinstance(data, list) else data.get("jobs", [])
        return [j for j in values if isinstance(j, dict)] if isinstance(values, list) else []
    except (OSError, ValueError, TypeError):
        return []


def roster(home: Path | None = None) -> dict[str, Any]:
    """Discover every installed bot, including newly created profiles."""
    home = home or Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))).expanduser()
    profiles = home / "profiles" if (home / "profiles").is_dir() else home
    installed = {p.name: p for p in profiles.iterdir() if p.is_dir() and (p / "profile.yaml").is_file()} if profiles.is_dir() else {}
    ordered = [key for key in BOT_ORDER if key in installed]
    ordered += sorted(key for key in installed if key not in BOT_ORDER)
    shared = _shared_jobs(home)

    cards = []
    for key in ordered:
        profile = installed[key]
        name, role, description = _profile_meta(profile)
        jobs = owned_jobs(key, profile, shared)
        enabled = [j for j in jobs if j.get("enabled", True) and j.get("state") not in ("paused", "completed")]
        failing = [j for j in enabled if (j.get("failure_streak") or 0) > 0 or j.get("last_status") not in (None, "ok", "success")]
        work = _latest_work(profile)
        activity = read_sessions(profile, limit=1)
        last_runs = [j["last_run_at"] for j in jobs if isinstance(j.get("last_run_at"), str)]
        latest_job = max((j for j in jobs if isinstance(j.get("last_run_at"), str)), key=lambda j: _timestamp(j["last_run_at"]), default=None)
        upcoming = sorted((j for j in enabled if isinstance(j.get("next_run_at"), str)), key=lambda j: _timestamp(j["next_run_at"]))
        active_now = bool(activity["active_now"])
        status = "needs-attention" if failing else "active" if active_now else "completed" if work["summary"] or last_runs or activity["latest_activity_at"] else "ready"
        if active_now:
            current_work = activity["current_title"] or "Working now"
        elif work["summary"]:
            current_work = work["summary"]
        elif latest_job:
            current_work = f"Latest result: {latest_job.get('name')}"
        elif activity["sessions"]:
            current_work = f"Latest session: {activity['sessions'][0]['title']}"
        else:
            current_work = "No recorded sessions or job results"
        cards.append({
            "id": key, "name": name, "role": role, "description": description,
            "status": status, "current_work": current_work,
            "last_work_at": _latest([work["last_work_at"], *last_runs, activity["latest_activity_at"]]),
            "latest_activity_title": activity["sessions"][0]["title"] if activity["sessions"] else None,
            "active_now": active_now,
            "activity_available": activity["available"],
            "scheduled_jobs": len(jobs), "active_jobs": len(enabled),
            "failing_jobs": len(failing),
            "next_run_at": upcoming[0]["next_run_at"] if upcoming else None,
        })
    return {"agents": cards, "count": len(cards), "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
