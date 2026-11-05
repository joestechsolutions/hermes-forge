"""Regression tests for the live Command Center audit fixes."""
import asyncio
import json

from fastapi.testclient import TestClient

from dashboard.backend.services import command_center, systemd


def test_interval_cadence_is_not_mislabeled_daily():
    assert command_center._cadence({"kind": "cron", "expr": "*/3 * * * *"}) == "every 3m"
    assert command_center._cadence({"kind": "cron", "expr": "0 */2 * * *"}) == "every 2h"
    assert command_center._cadence({"kind": "cron", "expr": "0 9 * * 1-5"}) == "weekdays"


def test_summary_excludes_completed_and_catches_last_run_failure(monkeypatch):
    monkeypatch.setattr(command_center, "_load_jobs", lambda: [
        {"name": "healthy", "enabled": True, "state": "scheduled", "last_status": "ok"},
        {"name": "failed", "enabled": True, "state": "scheduled", "last_status": "error", "failure_streak": 0},
        {"name": "done", "enabled": True, "state": "completed", "last_status": "ok"},
    ])
    data = command_center.summary()
    assert data["live"] == 2
    assert data["failing"] == 1
    assert data["failing_names"] == ["failed"]


def test_report_lookup_rejects_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr(command_center, "OUTPUT_DIR", str(tmp_path))
    (tmp_path / "secret.txt").write_text("do not expose")
    assert command_center.report_text("../secret.txt") is None
    assert command_center.report_text("valid-job", "../secret.txt") is None


def test_docker_inventory_marks_container_type(monkeypatch):
    async def fake_run(*args, **kwargs):
        return 0, json.dumps({"Names": "postiz", "State": "running", "Ports": "127.0.0.1:4007->4007/tcp"}) + "\n", ""
    monkeypatch.setattr(systemd, "_run", fake_run)
    rows = asyncio.run(systemd.check_docker_containers())
    assert rows == [{"name": "postiz", "state": "running", "kind": "docker", "port": 4007}]


def test_metrics_and_html_are_json_and_not_cached(monkeypatch):
    from dashboard.backend.services import auth_gate
    from dashboard.backend.main import app
    monkeypatch.setattr(auth_gate, "session_valid", lambda session: session == "test-session")
    client = TestClient(app)
    response = client.get("/api/v1/system/metrics", cookies={"cc_session": "test-session"})
    assert response.status_code == 200
    assert isinstance(response.json()["timestamp"], str)
    assert response.headers["cache-control"] == "no-store"
    page = client.get("/", cookies={"cc_session": "test-session"})
    assert page.status_code == 200
    assert page.headers["cache-control"] == "no-store"


def test_gateway_probe_uses_supported_systemctl_output(monkeypatch):
    from unittest.mock import MagicMock
    from dashboard.backend.services import agent_status
    seen = {}

    def fake_run(args, **kwargs):
        seen["args"] = args
        return MagicMock(returncode=0, stdout="active\n")

    monkeypatch.setattr(agent_status.subprocess, "run", fake_run)
    assert agent_status.check_hermes_agent()["status"] == "active"
    assert "--output=env" not in seen["args"]
    assert "--property=ActiveState" in seen["args"]
