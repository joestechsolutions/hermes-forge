"""Agent drill-down: real session activity, owned jobs, outputs, and privacy."""
import json
import sqlite3
import time

import pytest
from fastapi.testclient import TestClient

from dashboard.backend.services import agent_activity, agent_roster, command_center


def make_agent_home(tmp_path):
    home = tmp_path / "hermes"
    profile = home / "profiles" / "ledger"
    profile.mkdir(parents=True)
    (profile / "profile.yaml").write_text("display_name: Ledger\ndescription: Revenue analyst\n")
    now = time.time()
    database = sqlite3.connect(profile / "state.db")
    database.execute(
        """CREATE TABLE sessions (
            id TEXT, title TEXT, last_activity_description TEXT, last_activity_at REAL,
            started_at REAL, ended_at REAL, message_count INTEGER,
            tool_call_count INTEGER, model TEXT, archived INTEGER
        )"""
    )
    database.execute("CREATE TABLE session_turn_leases (conversation_id TEXT, expires_at REAL)")
    database.execute("CREATE TABLE messages (session_id TEXT, role TEXT, content TEXT, timestamp REAL, active INTEGER, compacted INTEGER)")
    database.execute(
        "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)",
        ("s-active", "Reconcile affiliate results", "Checking affiliate monitor output", now, now - 20, None, 8, 3, "kimi-k3.1-pro:cloud"),
    )
    database.execute(
        "INSERT INTO sessions VALUES (?, ?, '', ?, ?, ?, ?, ?, ?, 0)",
        ("s-old", "Earlier revenue review", now - 5000, now - 5100, now - 4900, 4, 1, "glm-5.3:cloud"),
    )
    database.executemany(
        "INSERT INTO messages VALUES (?, ?, ?, ?, 1, 0)",
        [
            ("s-active", "user", "private user prompt", now - 15),
            ("s-active", "assistant", "Reconciled 84 links; no payout total claimed.", now),
            ("s-old", "assistant", "Completed the earlier review.", now - 4900),
        ],
    )
    database.commit()
    database.close()
    cron = home / "cron"
    cron.mkdir()
    (cron / "jobs.json").write_text(json.dumps({"jobs": [{
        "id": "aff", "name": "renfaire_affiliate_watch", "skill": "renfaire-directory-site",
        "enabled": True, "state": "scheduled", "last_status": "ok",
        "last_run_at": "2026-11-04T14:51:51-08:00", "next_run_at": "2026-11-04T16:51:00-08:00",
        "schedule": {"kind": "cron", "expr": "51 * * * *"},
        "prompt": "private prompt", "api_key": "never-serialize",
    }]}))
    output = cron / "output" / "aff"
    output.mkdir(parents=True)
    (output / "report.md").write_text("# Job Report\n\nmetadata\n\n## Response\nChecked affiliate events; no payout total claimed.\n")
    return home


def test_detail_shows_real_current_activity_and_owned_output(tmp_path, monkeypatch):
    home = make_agent_home(tmp_path)
    monkeypatch.setattr(command_center, "OUTPUT_DIR", str(home / "cron" / "output"))
    detail = agent_activity.agent_detail("ledger", home)
    assert detail["active_now"] is True
    assert detail["current_title"] == "Checking affiliate monitor output"
    assert detail["agent"]["status"] == "active"
    assert detail["sessions"][0]["tool_call_count"] == 3
    assert detail["sessions"][0]["model"] == "kimi-k3.1-pro:cloud"
    assert detail["sessions"][0]["result"] == "Reconciled 84 links; no payout total claimed."
    assert detail["sessions"][1]["result"] == "Completed the earlier review."
    assert len(detail["jobs"]) == 1
    assert detail["jobs"][0]["latest_output"]["body"] == "Checked affiliate events; no payout total claimed."
    serialized = json.dumps(detail)
    assert "private prompt" not in serialized
    assert "private user prompt" not in serialized
    assert "never-serialize" not in serialized
    assert "system_prompt" not in serialized
    assert "chat_id" not in serialized


def test_final_result_redacts_secret_shaped_values():
    from dashboard.backend.services.agent_sessions import _result
    result, truncated = _result("api_key = abcdefghijklmnop\nBearer abcdefghijklmnop\nDone")
    assert result == "api_key = [REDACTED]\n[REDACTED]\nDone"
    assert truncated is False


def test_old_ended_session_is_not_mislabeled_working(tmp_path, monkeypatch):
    home = make_agent_home(tmp_path)
    database = sqlite3.connect(home / "profiles" / "ledger" / "state.db")
    database.execute("UPDATE sessions SET ended_at = last_activity_at + 10")
    database.commit()
    database.close()
    monkeypatch.setattr(command_center, "OUTPUT_DIR", str(home / "cron" / "output"))
    detail = agent_activity.agent_detail("ledger", home)
    assert detail["active_now"] is False
    assert detail["current_title"] is None
    assert detail["agent"]["status"] == "completed"


def test_detail_unknown_agent_fails_closed(tmp_path):
    with pytest.raises(KeyError):
        agent_activity.agent_detail("missing", tmp_path)


def test_detail_route_auth_and_static_status_route_are_not_shadowed(monkeypatch):
    from dashboard.backend.main import app
    from dashboard.backend.services import auth_routes
    from dashboard.backend.api import routes
    calls = []
    def fake_detail(profile_id):
        calls.append(profile_id)
        if profile_id != "ledger":
            raise KeyError(profile_id)
        return {"agent": {"id": profile_id}, "sessions": [], "jobs": []}
    monkeypatch.setattr(routes.agent_activity, "agent_detail", fake_detail)
    monkeypatch.setattr(routes, "check_all_agents", lambda: [{"agent": "hermes", "status": "active"}])
    monkeypatch.setattr(auth_routes.auth_gate, "session_valid", lambda session: session == "ok")
    client = TestClient(app, base_url="https://testserver")
    assert client.get("/api/v1/agents/ledger", cookies={"cc_session": "ok"}).status_code == 200
    assert client.get("/api/v1/agents/missing", cookies={"cc_session": "ok"}).status_code == 404
    status = client.get("/api/v1/agents/status", cookies={"cc_session": "ok"})
    assert status.status_code == 200
    assert status.json()[0]["agent"] == "hermes"
    assert calls == ["ledger", "missing"]
    assert client.get("/api/v1/agents/ledger").status_code == 401
