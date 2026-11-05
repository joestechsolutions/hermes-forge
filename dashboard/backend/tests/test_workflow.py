"""Sanitized lead/worker/advisor workflow from the real delegation ledger."""
import json
import os
import sqlite3
import time

from fastapi.testclient import TestClient

from dashboard.backend.services.workflow import read_workflow


def make_workflow_home(tmp_path):
    home = tmp_path / "hermes"
    home.mkdir()
    now = time.time()
    database = sqlite3.connect(home / "state.db")
    database.execute("CREATE TABLE sessions (id TEXT, title TEXT, model TEXT, last_activity_at REAL, ended_at REAL, hidden INTEGER, archived INTEGER)")
    database.execute("CREATE TABLE messages (session_id TEXT, role TEXT, tool_name TEXT, timestamp REAL)")
    database.execute("CREATE TABLE session_turn_leases (conversation_id TEXT, expires_at REAL)")
    database.execute("""CREATE TABLE async_delegations (
        delegation_id TEXT, parent_session_id TEXT, state TEXT, delivery_state TEXT,
        dispatched_at REAL, completed_at REAL, updated_at REAL, delivered_at REAL,
        owner_pid INTEGER, task_json TEXT, event_json TEXT
    )""")
    database.execute("INSERT INTO sessions VALUES ('lead-session', 'Build workflow', 'kimi-k3.1-pro:cloud', ?, NULL, 0, 0)", (now,))
    database.execute("INSERT INTO session_turn_leases VALUES ('lead-session', ?)", (now + 60,))
    database.executemany("INSERT INTO messages VALUES ('lead-session', 'tool', ?, ?)", [("delegate_task", now), ("search_files", now - 5)])
    goals = [
        "[workflow_role=worker] [workflow_stage=build] [workflow_label=UI build] private goal with api_key=never-serialize",
        "[workflow_role=advisor] [workflow_stage=verify] [workflow_label=Engineering review] private review prompt",
    ]
    results = [
        {"task_index": 0, "status": "completed", "model": "glm-5.3:cloud", "duration_seconds": 20.0, "exit_reason": "completed", "schema_valid": True, "summary": "private worker summary"},
        {"task_index": 1, "status": "completed", "model": "glm-5.3:cloud", "duration_seconds": 15.0, "exit_reason": "completed", "schema_valid": True, "summary": "VERDICT: CLEAN"},
    ]
    database.execute(
        "INSERT INTO async_delegations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "deleg_test", "lead-session", "completed", "delivered", now - 30, now - 5, now - 4, now - 4, os.getpid(),
            json.dumps({"goals": goals, "model": "glm-5.3:cloud", "origin_session": "chat_id=0000000000"}),
            json.dumps({"status": "completed", "results": results}),
        ),
    )
    database.commit()
    database.close()
    manifest = home / "cache" / "delegation" / "live" / "deleg_test"
    manifest.mkdir(parents=True)
    (manifest / "manifest.json").write_text(json.dumps({
        "delegation_id": "deleg_test", "task_count": 2,
        "tasks": [
            {"index": 0, "status": "completed", "model": "glm-5.3:cloud", "goal": "private cached goal"},
            {"index": 1, "status": "completed", "model": "glm-5.3:cloud", "goal": "private cached review"},
        ],
    }))
    return home


def test_completed_workflow_has_explicit_roles_and_real_verification(tmp_path):
    data = read_workflow(make_workflow_home(tmp_path))
    assert data["available"] is True
    assert data["lead"]["name"] == "Lurkr"
    assert data["lead"]["active_now"] is True
    assert data["lead"]["current_action"] == "Delegating work"
    assert data["run"]["state"] == "completed"
    assert data["run"]["active_now"] is False
    assert [task["label"] for task in data["workers"]] == ["UI build"]
    assert [task["label"] for task in data["advisors"]] == ["Engineering review"]
    assert data["verification"]["state"] == "passed"
    assert data["verification"]["label"] == "Engineering review passed"
    serialized = json.dumps(data)
    for forbidden in ("private goal", "private review", "private cached", "never-serialize", "chat_id", "origin_session", "summary", "VERDICT: CLEAN"):
        assert forbidden not in serialized


def test_stale_running_batch_is_not_active_and_missing_manifest_is_tolerated(tmp_path):
    home = make_workflow_home(tmp_path)
    database = sqlite3.connect(home / "state.db")
    database.execute("UPDATE async_delegations SET state='running', delivery_state='pending', completed_at=NULL, delivered_at=NULL")
    database.execute("UPDATE async_delegations SET updated_at=?, owner_pid=?, event_json=?", (time.time() - 500, 99999999, json.dumps({"status": "running", "results": []})))
    database.commit()
    database.close()
    (home / "cache" / "delegation" / "live" / "deleg_test" / "manifest.json").write_text("{torn")
    data = read_workflow(home)
    assert data["run"]["state"] == "stale"
    assert data["run"]["stale_reason"] == "owner-and-update-stale"
    assert data["run"]["active_now"] is False
    assert all(task["active_now"] is False for task in data["workers"] + data["advisors"])


def test_recent_update_with_dead_owner_has_a_distinct_stale_reason(tmp_path):
    home = make_workflow_home(tmp_path)
    database = sqlite3.connect(home / "state.db")
    database.execute("UPDATE async_delegations SET state='running', delivery_state='pending', completed_at=NULL, delivered_at=NULL, updated_at=?, owner_pid=?, event_json=?", (time.time(), 99999999, json.dumps({"status": "running", "results": []})))
    database.commit()
    database.close()
    data = read_workflow(home)
    assert data["run"]["state"] == "stale"
    assert data["run"]["stale_reason"] == "owner-not-running"
    assert data["run"]["active_now"] is False


def test_unattributed_delegation_is_never_attached_to_the_lead(tmp_path):
    home = make_workflow_home(tmp_path)
    database = sqlite3.connect(home / "state.db")
    row = database.execute("SELECT * FROM async_delegations").fetchone()
    values = list(row)
    values[0] = "deleg_unattributed"
    values[1] = ""
    values[4] = time.time() + 100
    database.execute("INSERT INTO async_delegations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", values)
    database.commit()
    database.close()
    data = read_workflow(home)
    assert data["run"]["state"] == "completed"
    assert len(data["workers"]) == 1


def test_missing_database_degrades_without_inventing_work(tmp_path):
    data = read_workflow(tmp_path)
    assert data["available"] is True
    assert data["lead"]["active_now"] is False
    assert data["workers"] == []
    assert data["verification"]["state"] == "not-recorded"


def test_workflow_route_requires_auth(monkeypatch):
    from dashboard.backend.main import app
    from dashboard.backend.services import auth_routes
    from dashboard.backend.api import routes
    monkeypatch.setattr(auth_routes.auth_gate, "session_valid", lambda session: session == "ok")
    monkeypatch.setattr(routes.workflow, "read_workflow", lambda home: {"available": True, "workers": [], "advisors": []})
    client = TestClient(app, base_url="https://testserver")
    assert client.get("/api/v1/workflow").status_code == 401
    response = client.get("/api/v1/workflow", cookies={"cc_session": "ok"})
    assert response.status_code == 200
    assert response.json()["available"] is True
