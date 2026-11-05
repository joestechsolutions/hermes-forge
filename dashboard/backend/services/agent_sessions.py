"""Read-only, bounded Hermes session activity for dashboard agent views.

Only task-level metadata is returned. Message bodies, prompts, chat identifiers,
credentials, and connection details never leave this module.
"""
from __future__ import annotations

import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ACTIVE_WINDOW_S = 120


def _clean(value: Any, limit: int = 180) -> str | None:
    if not isinstance(value, str):
        return None
    text = " ".join(value.replace("\x00", " ").split()).strip()
    return text[:limit] if text else None


def _iso(value: Any) -> str | None:
    try:
        return datetime.fromtimestamp(float(value), timezone.utc).isoformat(timespec="seconds")
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def read_sessions(profile: Path, limit: int = 5) -> dict[str, Any]:
    path = profile / "state.db"
    empty = {
        "available": True,
        "active_now": False,
        "latest_activity_at": None,
        "current_title": None,
        "sessions": [],
    }
    if not path.is_file():
        return empty
    try:
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=0.25)
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """SELECT title, last_activity_description, last_activity_at,
                      started_at, ended_at, message_count, tool_call_count, model
               FROM sessions
               WHERE coalesce(archived, 0) = 0
               ORDER BY last_activity_at DESC LIMIT ?""",
            (max(1, min(limit, 10)),),
        ).fetchall()
        try:
            leases = connection.execute(
                "SELECT count(*) FROM session_turn_leases WHERE expires_at > ?",
                (time.time(),),
            ).fetchone()[0]
        except sqlite3.Error:
            leases = 0
        connection.close()
    except (sqlite3.Error, OSError):
        return {**empty, "available": False}

    now = time.time()
    sessions = []
    for row in rows:
        last_raw = row["last_activity_at"]
        try:
            recent_unended = row["ended_at"] is None and float(last_raw) >= now - ACTIVE_WINDOW_S
        except (TypeError, ValueError):
            recent_unended = False
        title = _clean(row["title"]) or "Untitled agent session"
        activity = _clean(row["last_activity_description"], 240)
        sessions.append({
            "title": title,
            "activity": activity,
            "last_activity_at": _iso(last_raw),
            "started_at": _iso(row["started_at"]),
            "ended_at": _iso(row["ended_at"]),
            "message_count": max(0, int(row["message_count"] or 0)),
            "tool_call_count": max(0, int(row["tool_call_count"] or 0)),
            "model": _clean(row["model"], 100),
            "active": bool(recent_unended),
        })
    latest = sessions[0] if sessions else None
    active_now = bool(leases > 0 or (latest and latest["active"]))
    current_title = None
    if active_now and latest:
        current_title = latest["activity"] or latest["title"] if latest["ended_at"] is None else "Active agent session"
    return {
        "available": True,
        "active_now": active_now,
        "latest_activity_at": latest["last_activity_at"] if latest else None,
        "current_title": current_title,
        "sessions": sessions,
    }
