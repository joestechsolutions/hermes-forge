"""Tests for agent status probes."""
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from dashboard.backend.services.agent_status import (
    check_hermes_agent,
    check_opencode,
    check_claude_code,
    check_mempalace,
    check_all_agents,
)


# --- Hermes tests ---


@patch("backend.services.agent_status.subprocess.run")
def test_check_hermes_running(mock_run):
    mock_run.return_value = MagicMock(stdout="ActiveState=active\nLOAD_STATE=loaded\n")
    result = check_hermes_agent()
    assert result["agent"] == "hermes"
    assert result["status"] == "active"


@patch("backend.services.agent_status.subprocess.run")
def test_check_hermes_stopped(mock_run):
    mock_run.return_value = MagicMock(stdout="ActiveState=inactive\nLOAD_STATE=loaded\n")
    result = check_hermes_agent()
    assert result["agent"] == "hermes"
    assert result["status"] == "stopped"


# --- OpenCode tests ---


@patch("backend.services.agent_status.shutil.which")
def test_check_opencode_found(mock_which):
    """OpenCode found but no session dir or pgrep returns empty."""
    mock_which.return_value = "/usr/bin/opencode"
    with patch("backend.services.agent_status.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="1234 opencode")
        with patch("backend.services.agent_status.Path") as mock_path_cls:
            # session_dir.exists() -> False
            mock_session_dir = MagicMock(spec=Path)
            mock_session_dir.exists.return_value = False
            mock_home = MagicMock()
            mock_home.__truediv__.return_value = mock_session_dir
            mock_path_cls.home.return_value = mock_home
            result = check_opencode()
    assert result["agent"] == "opencode"
    assert result["status"] == "running"
    assert result["path"] == "/usr/bin/opencode"


@patch("backend.services.agent_status.shutil.which")
def test_check_opencode_not_found(mock_which):
    mock_which.return_value = None
    result = check_opencode()
    assert result["agent"] == "opencode"
    assert result["status"] == "not_found"


# --- Claude Code tests ---


@patch("backend.services.agent_status.shutil.which")
def test_check_claude_code_found(mock_which):
    mock_which.return_value = "/usr/local/bin/claude"
    with patch("backend.services.agent_status.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="1234 /usr/local/bin/claude --something"
        )
        result = check_claude_code()
    assert result["agent"] == "claude_code"
    assert result["status"] == "running"
    assert result["path"] == "/usr/local/bin/claude"


@patch("backend.services.agent_status.shutil.which")
def test_check_claude_code_not_found(mock_which):
    mock_which.return_value = None
    result = check_claude_code()
    assert result["agent"] == "claude_code"
    assert result["status"] == "not_found"


# --- MemPalace tests ---


@patch("backend.services.agent_status.subprocess.run")
@patch("backend.services.agent_status.Path")
def test_check_mempalace_found_venv(mock_path_cls, mock_run):
    mock_run.return_value = MagicMock(returncode=0)

    # Build a chain: Path.home() / ".mempalace" / "venv" / "bin" / "python"
    mock_venv_python = MagicMock(spec=Path)
    mock_venv_python.exists.return_value = True  # venv ready

    mock_vbin = MagicMock(spec=Path)
    mock_vbin.__truediv__.return_value = mock_venv_python

    mock_venv = MagicMock(spec=Path)
    mock_venv.__truediv__.return_value = mock_vbin

    mock_mempalace = MagicMock(spec=Path)
    mock_mempalace.exists.return_value = True  # dir exists
    mock_mempalace.__truediv__.return_value = mock_venv

    mock_home = MagicMock(spec=Path)
    mock_home.__truediv__.return_value = mock_mempalace

    mock_path_cls.home.return_value = mock_home

    result = check_mempalace()
    assert result["agent"] == "mempalace"
    assert result["status"] == "running"
    assert result["venv_ready"] is True


@patch("backend.services.agent_status.Path")
def test_check_mempalace_not_found(mock_path_cls):
    mock_mempalace = MagicMock(spec=Path)
    mock_mempalace.exists.return_value = False
    mock_home = MagicMock(spec=Path)
    mock_home.__truediv__.return_value = mock_mempalace
    mock_path_cls.home.return_value = mock_home
    result = check_mempalace()
    assert result["agent"] == "mempalace"
    assert result["status"] == "not_found"


# --- check_all_agents test ---


@patch("backend.services.agent_status.check_mempalace")
@patch("backend.services.agent_status.check_claude_code")
@patch("backend.services.agent_status.check_opencode")
@patch("backend.services.agent_status.check_hermes_agent")
def test_check_all_agents(mock_hermes, mock_opencode, mock_claude, mock_mempalace):
    mock_hermes.return_value = {"agent": "hermes", "status": "active", "state_db_age": None}
    mock_opencode.return_value = {"agent": "opencode", "status": "idle", "path": "/bin/opencode", "sessions": None}
    mock_claude.return_value = {"agent": "claude_code", "status": "idle", "path": "/bin/claude"}
    mock_mempalace.return_value = {"agent": "mempalace", "status": "stopped", "venv_ready": True}

    results = check_all_agents()

    assert len(results) == 4
    agent_names = [r["agent"] for r in results]
    assert "hermes" in agent_names
    assert "opencode" in agent_names
    assert "claude_code" in agent_names
    assert "mempalace" in agent_names

    # Verify each individual check was called
    mock_hermes.assert_called_once()
    mock_opencode.assert_called_once()
    mock_claude.assert_called_once()
    mock_mempalace.assert_called_once()
