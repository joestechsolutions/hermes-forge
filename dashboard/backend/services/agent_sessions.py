"""Read-only, bounded Hermes session activity for dashboard agent views.

Task metadata and final assistant results are allowed. User messages, prompts,
tool arguments, chat identifiers, credentials, and connection details are not.
"""
from __future__ import annotations

import re
import sqlite3
import time
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ACTIVE_WINDOW_S = 120
RESULT_LIMIT = 6000
SECRET_ASSIGNMENT = re.compile(
    r"(?im)^(\s*(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|secret)\s*[:=]\s*)\S+"
)
SECRET_TOKEN = re.compile(r"(?i)\b(?:sk-[A-Za-z0-9_-]{12,}|Bearer\s+[A-Za-z0-9._~+/-]{12,})")


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


def _result(value: Any) -> tuple[str | None, bool]:
    if not isinstance(value, str):
        return None, False
    text = SECRET_ASSIGNMENT.sub(r"\1[REDACTED]", value.replace("\x00", "").strip())
    text = SECRET_TOKEN.sub("[REDACTED]", text)
    return text[:RESULT_LIMIT] or None, len(text) > RESULT_LIMIT


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
        with closing(sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=0.25)) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """SELECT id, title, last_activity_description, last_activity_at,
                          started_at, ended_at, message_count, tool_call_count, model
                   FROM sessions
                   WHERE coalesce(archived, 0) = 0
                   ORDER BY last_activity_at DESC LIMIT ?""",
                (max(1, min(limit, 10)),),
            ).fetchall()
            results: dict[str, tuple[str | None, bool]] = {}
            for row in rows:
                try:
                    message = connection.execute(
                        """SELECT content FROM messages
                           WHERE session_id = ? AND role = 'assistant'
                             AND coalesce(active, 1) = 1 AND coalesce(compacted, 0) = 0
                           ORDER BY timestamp DESC LIMIT 1""",
                        (row["id"],),
                    ).fetchone()
                    results[str(row["id"])] = _result(message["content"] if message else None)
                except sqlite3.Error:
                    results[str(row["id"])] = (None, False)
            try:
                leases = connection.execute(
                    "SELECT count(*) FROM session_turn_leases WHERE expires_at > ?",
                    (time.time(),),
                ).fetchone()[0]
            except sqlite3.Error:
                leases = 0
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
        result, truncated = results.get(str(row["id"]), (None, False))
        sessions.append({
            "title": title,
            "activity": activity,
            "result": result,
            "result_truncated": truncated,
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
