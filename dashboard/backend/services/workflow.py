"""Truthful lead → workers → advisor → verification workflow view.

The main Hermes delegation ledger is authoritative. Cache manifests only enrich
per-task state. Explicit workflow tags classify work; prompt text, tool args,
chat identifiers, logs, and result summaries never leave this module.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import time
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dashboard.backend.services.agent_sessions import _clean, _iso

ACTIVE_WINDOW_S = 120
ROLE_RE = re.compile(r"\[workflow_role=(worker|advisor)\]", re.I)
STAGE_RE = re.compile(r"\[workflow_stage=([a-z_]+)\]", re.I)
LABEL_RE = re.compile(r"\[workflow_label=([A-Za-z0-9 _-]{1,48})\]")
ACTIVE_STATES = {"running", "in_progress", "active"}
TOOL_LABELS = {
    "delegate_task": "Delegating work",
    "search_files": "Searching the workspace",
    "read_file": "Reading project files",
    "write_file": "Writing project files",
    "patch": "Applying a focused edit",
    "terminal": "Running a terminal command",
    "execute_code": "Running a command",
    "browser_exec": "Checking the browser",
    "vision_analyze": "Reviewing visual evidence",
    "skill_view": "Loading a workflow skill",
    "tool_call": "Using an integration",
    "todo_list": "Updating the work plan",
}


def _tool_label(name: Any) -> str:
    value = str(name or "")
    return TOOL_LABELS.get(value, f"Using {value.replace('_', ' ')}" if value else "No tool activity recorded")


def _tag(pattern: re.Pattern[str], text: str, default: str) -> str:
    match = pattern.search(text)
    return (match.group(1).strip() if match else default).lower()


def _label(text: str, default: str) -> str:
    match = LABEL_RE.search(text)
    return (_clean(match.group(1), 48) or default) if match else default


def _manifest(home: Path, delegation_id: str) -> dict[str, Any]:
    path = home / "cache" / "delegation" / "live" / delegation_id / "manifest.json"
    try:
        value = json.loads(path.read_text())
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _pid_alive(pid: Any) -> bool:
    try:
        os.kill(int(pid), 0)
        return int(pid) > 0
    except (TypeError, ValueError, ProcessLookupError, PermissionError, OSError):
        return False


def _task_views(row: sqlite3.Row, task_json: dict[str, Any], event_json: dict[str, Any], manifest: dict[str, Any], batch_active: bool) -> list[dict[str, Any]]:
    raw_goals = task_json.get("goals")
    raw_results = event_json.get("results")
    raw_manifest_tasks = manifest.get("tasks")
    goals = raw_goals if isinstance(raw_goals, list) else []
    results = raw_results if isinstance(raw_results, list) else []
    by_index = {item.get("task_index"): item for item in results if isinstance(item, dict)}
    manifest_tasks = raw_manifest_tasks if isinstance(raw_manifest_tasks, list) else []
    manifest_by_index = {item.get("index"): item for item in manifest_tasks if isinstance(item, dict)}
    count = max(len(goals), len(results), len(manifest_tasks), int(manifest.get("task_count") or 0))
    tasks = []
    for index in range(count):
        goal = goals[index] if index < len(goals) and isinstance(goals[index], str) else ""
        result = by_index.get(index, {})
        cached = manifest_by_index.get(index, {})
        status = str(result.get("status") or cached.get("status") or "").lower()
        if not status:
            status = "running" if batch_active else "unknown"
        active = batch_active and status in ACTIVE_STATES
        tasks.append({
            "index": index,
            "label": _label(goal, f"Delegated task {index + 1}"),
            "role": _tag(ROLE_RE, goal, "worker"),
            "stage": _tag(STAGE_RE, goal, "work"),
            "status": status,
            "active_now": active,
            "model": _clean(result.get("model") or cached.get("model") or task_json.get("model"), 100),
            "duration_seconds": max(0, int(float(result.get("duration_seconds") or 0))),
            "exit_reason": _clean(result.get("exit_reason") or cached.get("exit_reason"), 80),
            "schema_valid": result.get("schema_valid") if isinstance(result.get("schema_valid"), bool) else None,
            "summary": result.get("summary") if isinstance(result.get("summary"), str) else "",
        })
    return tasks


def _public_task(task: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in task.items() if key != "summary"}


def _verification(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = [task for task in tasks if task["role"] == "advisor" and task["stage"] in {"verify", "review", "before_done"}]
    if not candidates:
        return {"state": "not-recorded", "label": "No verification checkpoint recorded", "at": None}
    task = candidates[-1]
    summary = task["summary"].strip()
    passed = False
    try:
        parsed = json.loads(summary) if summary else {}
        verdict = str(parsed.get("verdict") or "").lower() if isinstance(parsed, dict) else ""
        passed = verdict == "clean" or (parsed.get("pass") is True and not parsed.get("blockers") and not parsed.get("blocking"))
    except (ValueError, TypeError):
        passed = "VERDICT: CLEAN" in summary.upper()
    if task["status"] != "completed":
        state = "running" if task["active_now"] else "unknown"
        label = f"{task['label']} {state}"
    else:
        state = "passed" if passed else "completed"
        label = f"{task['label']} passed" if passed else f"{task['label']} completed; verdict not marked clean"
    return {"state": state, "label": label, "at": None}


def read_workflow(home: Path) -> dict[str, Any]:
    empty = {
        "available": True,
        "lead": {"name": "Lurkr", "role": "Lead orchestrator", "active_now": False, "current_action": "No session activity recorded", "model": None, "last_activity_at": None},
        "run": None,
        "workers": [],
        "advisors": [],
        "verification": {"state": "not-recorded", "label": "No verification checkpoint recorded", "at": None},
        "events": [],
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    path = home / "state.db"
    if not path.is_file():
        return empty
    try:
        with closing(sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=0.25)) as connection:
            connection.row_factory = sqlite3.Row
            session = connection.execute(
                """SELECT id, title, model, last_activity_at, ended_at
                   FROM sessions WHERE coalesce(archived,0)=0 AND coalesce(hidden,0)=0
                   ORDER BY last_activity_at DESC LIMIT 1"""
            ).fetchone()
            if session is None:
                return empty
            now = time.time()
            try:
                leases = connection.execute("SELECT count(*) FROM session_turn_leases WHERE expires_at > ?", (now,)).fetchone()[0]
            except sqlite3.Error:
                leases = 0
            try:
                recent_unended = session["ended_at"] is None and float(session["last_activity_at"]) >= now - ACTIVE_WINDOW_S
            except (TypeError, ValueError):
                recent_unended = False
            tool_rows = connection.execute(
                """SELECT role, tool_name, timestamp FROM messages
                   WHERE session_id=? AND tool_name IS NOT NULL
                   ORDER BY timestamp DESC LIMIT 10""",
                (session["id"],),
            ).fetchall()
            latest_tool = tool_rows[0] if tool_rows else None
            lead = {
                "name": "Lurkr",
                "role": "Lead orchestrator",
                "active_now": bool(leases > 0 or recent_unended),
                "current_action": _tool_label(latest_tool["tool_name"] if latest_tool else None),
                "model": _clean(session["model"], 100),
                "last_activity_at": _iso(session["last_activity_at"]),
            }
            row = connection.execute(
                """SELECT delegation_id, state, delivery_state, dispatched_at, completed_at,
                          updated_at, delivered_at, owner_pid, task_json, event_json
                   FROM async_delegations WHERE parent_session_id=?
                   ORDER BY dispatched_at DESC LIMIT 1""",
                (session["id"],),
            ).fetchone()
            events = [{
                "actor": "Lurkr",
                "action": _tool_label(item["tool_name"]),
                "at": _iso(item["timestamp"]),
                "kind": "lead-tool",
            } for item in tool_rows]
            if row is None:
                return {**empty, "lead": lead, "events": events[:10]}

            task_json = json.loads(row["task_json"] or "{}")
            event_json = json.loads(row["event_json"] or "{}")
            if not isinstance(task_json, dict):
                task_json = {}
            if not isinstance(event_json, dict):
                event_json = {}
            manifest = _manifest(home, str(row["delegation_id"]))
            updated = float(row["updated_at"] or row["dispatched_at"] or 0)
            batch_active = row["state"] == "running" and now - updated <= ACTIVE_WINDOW_S and _pid_alive(row["owner_pid"])
            run_state = str(row["state"] or "unknown")
            if run_state == "running" and not batch_active:
                run_state = "stale"
            run = {
                "state": run_state,
                "delivery_state": _clean(row["delivery_state"], 40),
                "active_now": batch_active,
                "dispatched_at": _iso(row["dispatched_at"]),
                "completed_at": _iso(row["completed_at"]),
                "updated_at": _iso(row["updated_at"]),
                "delivered_at": _iso(row["delivered_at"]),
            }
            tasks = _task_views(row, task_json, event_json, manifest, batch_active)
            workers = [_public_task(task) for task in tasks if task["role"] == "worker"]
            advisors = [_public_task(task) for task in tasks if task["role"] == "advisor"]
            verification = _verification(tasks)
            verification["at"] = run["completed_at"] if verification["state"] in {"passed", "completed"} else None
            events.extend([
                {"actor": "Lurkr", "action": f"Delegated {len(tasks)} task{'s' if len(tasks) != 1 else ''}", "at": run["dispatched_at"], "kind": "delegation"},
                {"actor": "Workflow", "action": f"Worker batch {run_state}", "at": run["completed_at"] or run["updated_at"], "kind": "delegation"},
            ])
            if run["delivered_at"]:
                events.append({"actor": "Lurkr", "action": "Received worker results for follow-up", "at": run["delivered_at"], "kind": "verification"})
            events = [event for event in events if event["at"]]
            events.sort(key=lambda event: event["at"], reverse=True)
            return {
                "available": True,
                "lead": lead,
                "run": run,
                "workers": workers,
                "advisors": advisors,
                "verification": verification,
                "events": events[:10],
                "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
    except (sqlite3.Error, OSError, ValueError, TypeError, json.JSONDecodeError):
        return {**empty, "available": False}
