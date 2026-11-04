"""Integration tests for the roster endpoint and its public-data boundary."""
import asyncio
import json

from dashboard.backend.services import agent_roster


def test_roster_endpoint_returns_ledger_and_only_safe_metadata(monkeypatch, tmp_path):
    profile = tmp_path / "profiles" / "ledger"
    (profile / "cron").mkdir(parents=True)
    (profile / "profile.yaml").write_text("display_name: Ledger\ndescription: Revenue analyst\n")
    (profile / "cron" / "jobs.json").write_text(json.dumps({"jobs": [{
        "name": "weekly-revenue", "enabled": True,
        "prompt": "private prompt", "last_status": "ok",
        "next_run_at": "2026-11-06T09:00:00-08:00",
    }]}))
    monkeypatch.setattr(agent_roster.os, "environ", {"HERMES_HOME": str(tmp_path)})

    async def read():
        from dashboard.backend.api.routes import agents_roster
        return await agents_roster()

    data = asyncio.run(read())
    assert data["count"] == 1
    ledger = data["agents"][0]
    assert ledger["name"] == "Ledger"
    assert ledger["status"] == "ready"
    assert ledger["scheduled_jobs"] == 1
    assert ledger["active_jobs"] == 1
    assert ledger["next_run_at"] == "2026-11-06T09:00:00-08:00"
    assert "private prompt" not in json.dumps(data)
