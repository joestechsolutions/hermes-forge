"""Live, read-only configuration shown by the dashboard.

Only non-secret model/role configuration is returned. The dashboard never reads or
returns an API key. Provider and agent checks use current process/session state.
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from dashboard.backend.services import agent_roster, agent_status
from dashboard.backend.services.model_providers import check_all_providers


def _model_config(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text()) or {}
        model = data.get("model", {}) if isinstance(data, dict) else {}
        return model if isinstance(model, dict) else {}
    except (OSError, ValueError, TypeError, yaml.YAMLError):
        return {}


def model_snapshot() -> dict[str, Any]:
    config = Path(os.environ.get("HERMES_CONFIG", str(Path.home() / ".hermes" / "config.yaml")))
    model = _model_config(config)
    name = model.get("default") if isinstance(model.get("default"), str) else None
    provider = model.get("provider") if isinstance(model.get("provider"), str) else None
    base_url = model.get("base_url") if isinstance(model.get("base_url"), str) else None
    # A model is configured, not assumed running merely because it is in config.
    models = [{"name": name, "provider": provider, "status": "configured",
               "description": "Primary conversation model — read from live config",
               "role": "Primary conversation"}] if name else []
    jobs_path = Path.home() / ".hermes/cron/jobs.json"
    counts: dict[tuple[str, str], int] = {}
    try:
        data = json.loads(jobs_path.read_text())
        jobs = data if isinstance(data, list) else data.get("jobs", [])
        for job in jobs:
            if isinstance(job, dict) and job.get("enabled", True) and job.get("state") not in ("paused", "completed"):
                key = (job.get("model") or name or "Unspecified", job.get("provider") or provider or "Unspecified")
                counts[key] = counts.get(key, 0) + 1
    except (OSError, ValueError, TypeError):
        jobs = []
    for (model, model_provider), count in sorted(counts.items()):
        if model != name:
            models.append({"name": model, "provider": model_provider, "status": "configured",
                           "description": f"Used by {count} enabled scheduled job(s)", "role": "Scheduled jobs"})
    return {"name": name, "provider": provider, "base_url": base_url,
            "source": "Live Hermes configuration", "models": models,
            "enabled_scheduled_jobs": sum(1 for job in jobs if isinstance(job, dict) and job.get("enabled", True) and job.get("state") not in ("paused", "completed"))}


async def overview() -> dict[str, Any]:
    agents = await asyncio.to_thread(agent_roster.roster)
    providers = await check_all_providers()
    runtime = await asyncio.to_thread(agent_status.check_all_agents)
    return {
        "model": model_snapshot(),
        "agents": agents["agents"],
        "runtime_agents": runtime,
        "providers": providers,
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
