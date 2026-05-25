"""Agent framework status probes for Hermes, OpenCode, Claude Code."""
import subprocess
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


def check_hermes_agent() -> Dict[str, Any]:
    """Check Hermes agent service status via systemctl."""
    try:
        result = subprocess.run(
            ["systemctl", "--user", "show", "hermes-gateway", "--output=env", "--no-pager"],
            capture_output=True, text=True, timeout=5
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {"agent": "hermes", "status": "error"}

    state_line = ""
    for line in result.stdout.split("\n"):
        if line.startswith("SERVICE_STATE="):
            state_line = line.split("=", 1)[1]
        elif line.startswith("ActiveState="):
            state_line = line.split("=", 1)[1]
    active = "active" if state_line in ("active", "running") else "stopped"

    state_db = Path.home() / ".hermes" / "state.db"
    last_activity = None
    if state_db.exists():
        stat = state_db.stat()
        last_activity = datetime.fromtimestamp(stat.st_mtime).isoformat()

    return {
        "agent": "hermes",
        "status": active,
        "state_db_age": last_activity,
    }


def check_opencode() -> Dict[str, Any]:
    """Check OpenCode availability via which + process check."""
    opencode_path = shutil.which("opencode")
    if not opencode_path:
        return {"agent": "opencode", "status": "not_found"}

    # Check for running sessions via pgrep
    running = False
    try:
        result = subprocess.run(
            ["pgrep", "-f", "opencode"],
            capture_output=True, text=True, timeout=5
        )
        running = result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass  # pgrep not found or timed out — treat as not running

    # Check session dir
    session_dir = Path.home() / ".opencode"
    session_info = None
    if session_dir.exists():
        sessions = list(session_dir.glob("session-*"))
        if sessions:
            session_info = {"count": len(sessions)}

    return {
        "agent": "opencode",
        "status": "running" if running else "idle",
        "path": opencode_path,
        "sessions": session_info,
    }


def check_claude_code() -> Dict[str, Any]:
    """Check Claude Code availability."""
    claude_path = shutil.which("claude")
    if not claude_path:
        return {"agent": "claude_code", "status": "not_found"}

    # Check for active Claude Code session
    has_session = False
    try:
        result = subprocess.run(
            ["pgrep", "-f", "claude", "-a"],
            capture_output=True, text=True, timeout=5
        )
        has_session = result.returncode == 0 and "claude" in result.stdout.lower()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass  # pgrep not found or timed out

    return {
        "agent": "claude_code",
        "status": "running" if has_session else "idle",
        "path": claude_path,
    }


def check_mempalace() -> Dict[str, Any]:
    """Check MemPalace availability."""
    mempalace_dir = Path.home() / ".mempalace"
    if not mempalace_dir.exists():
        return {"agent": "mempalace", "status": "not_found"}

    venv_python = mempalace_dir / "venv" / "bin" / "python"
    venv_exists = venv_python.exists() if venv_python else False

    running = False
    try:
        result = subprocess.run(
            ["pgrep", "-f", "mempalace"],
            capture_output=True, text=True, timeout=5
        )
        running = result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return {
        "agent": "mempalace",
        "status": "running" if running else "stopped",
        "venv_ready": venv_exists,
    }


def check_all_agents() -> List[Dict[str, Any]]:
    hermes = check_hermes_agent()
    opencode = check_opencode()
    claude = check_claude_code()
    mempalace = check_mempalace()
    return [hermes, opencode, claude, mempalace]
