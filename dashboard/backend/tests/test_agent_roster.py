"""Unit tests for the privacy-bounded, read-only agent roster."""
import json
from pathlib import Path

from dashboard.backend.services.agent_roster import roster


def test_ledger_is_visible_without_work_record(tmp_path):
    profile = tmp_path / "profiles" / "ledger"
    profile.mkdir(parents=True)
    (profile / "profile.yaml").write_text("display_name: Ledger\ndescription: Revenue analyst\n")
    data = roster(tmp_path)
    assert data["count"] == 1
    assert data["agents"][0]["name"] == "Ledger"
    assert data["agents"][0]["role"] == "RenFaire Revenue Analyst"
    assert data["agents"][0]["status"] == "ready"
    assert data["agents"][0]["scheduled_jobs"] == 0
    assert data["agents"][0]["current_work"] == "Ready — no work recorded yet"


def test_roster_reads_profile_jobs_and_failures_without_prompt_contents(tmp_path):
    profile = tmp_path / "profiles" / "sterlingcfo"
    (profile / "cron").mkdir(parents=True)
    (profile / "profile.yaml").write_text("display_name: Sterling CFO\ndescription: Finance\n")
    (profile / "journal").mkdir()
    (profile / "journal" / "2026-11-04.md").write_text("private work details")
    (profile / "cron" / "jobs.json").write_text(json.dumps({"jobs": [{
        "name": "monthly-review", "enabled": True, "failure_streak": 2,
        "last_status": "error", "prompt": "never expose this private prompt",
    }]}))
    data = roster(tmp_path)
    row = data["agents"][0]
    assert row["status"] == "needs-attention"
    assert row["scheduled_jobs"] == 1
    assert row["active_jobs"] == 1
    assert row["failing_jobs"] == 1
    assert row["current_work"] == "Latest work journal"
    assert "never expose" not in json.dumps(data)
    assert "private work details" not in json.dumps(data)


def test_roster_survives_malformed_job_state(tmp_path):
    profile = tmp_path / "profiles" / "atlaschiefofstaff"
    (profile / "cron").mkdir(parents=True)
    (profile / "profile.yaml").write_text("display_name: Atlas Chief Of Staff\ndescription: Coordination\n")
    (profile / "cron" / "jobs.json").write_text("not JSON")
    data = roster(tmp_path)
    assert data["count"] == 1
    assert data["agents"][0]["name"] == "Atlas"
    assert data["agents"][0]["status"] == "ready"


def test_new_profile_is_discovered_without_a_code_change(tmp_path):
    for key, display in (("ledger", "Ledger"), ("sparrow", "Sparrow"), ("newbot", "New Bot")):
        profile = tmp_path / "profiles" / key
        profile.mkdir(parents=True)
        (profile / "profile.yaml").write_text(f"display_name: {display}\ndescription: Test agent\n")
    data = roster(tmp_path)
    assert data["count"] == 3
    assert [a["name"] for a in data["agents"]] == ["Ledger", "Sparrow", "New Bot"]


def test_shared_scheduler_results_are_attributed_to_real_owners(tmp_path):
    for key in ("ledger", "sterlingcfo", "novacmo"):
        profile = tmp_path / "profiles" / key
        profile.mkdir(parents=True)
        (profile / "profile.yaml").write_text(f"display_name: {key}\n")
    jobs = [
        {"id": "aff", "name": "renfaire_affiliate_watch", "enabled": True, "state": "scheduled", "last_status": "ok", "last_run_at": "2026-11-04T14:51:51-08:00"},
        {"id": "cfo", "name": "jts_cfo_weekly_review", "skill": "jts-cfo", "enabled": True, "state": "scheduled", "last_status": "ok"},
        {"id": "draft", "name": "content_draft", "skill": "joe-content-lane", "enabled": True, "state": "scheduled", "last_status": "ok"},
    ]
    import json
    cron = tmp_path / "cron"
    cron.mkdir()
    (cron / "jobs.json").write_text(json.dumps({"jobs": jobs}))
    agents = {a["id"]: a for a in roster(tmp_path)["agents"]}
    assert agents["ledger"]["scheduled_jobs"] == 1
    assert agents["ledger"]["current_work"] == "Latest result: renfaire_affiliate_watch"
    assert agents["ledger"]["last_work_at"] == "2026-11-04T14:51:51-08:00"
    assert agents["sterlingcfo"]["scheduled_jobs"] == 1
    assert agents["novacmo"]["scheduled_jobs"] == 1
