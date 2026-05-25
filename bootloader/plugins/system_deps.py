"""
System Dependencies Plugin

Installs system dependencies via platform-appropriate package manager.
Linux: apt-get | macOS: Homebrew
"""

import os
import subprocess
from typing import Any, Dict, List

from bootloader.lib.platform import (
    IS_MACOS, IS_LINUX, IS_WSL,
    pkg_install, pkg_update, pkg_clean, pkg_ensure_brew,
)


# Commands to check for presence
REQUIRED_COMMANDS = [
    "curl", "wget", "git", "python3", "pip", "make", "gcc",
    "jq", "openssl", "unzip",
]

# macOS doesn't have these
REQUIRED_COMMANDS_MACOS = [
    "curl", "git", "python3", "pip3", "make",
    "jq", "openssl", "unzip",
]


def command_exists(cmd: str) -> bool:
    try:
        subprocess.run(["which", cmd], capture_output=True, check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def _get_required_commands() -> List[str]:
    if IS_MACOS:
        return REQUIRED_COMMANDS_MACOS
    cmds = list(REQUIRED_COMMANDS)
    if IS_WSL:
        cmds = [c for c in cmds if c != "gcc"]  # WSL may not have gcc
    return cmds


def _missing_commands() -> List[str]:
    missing = []
    for cmd in _get_required_commands():
        if not command_exists(cmd):
            missing.append(cmd)
    return missing


def hook_check_prerequisites(context: Dict[str, Any]) -> bool:
    """Check if all required commands are installed."""
    missing = _missing_commands()
    if missing:
        print(f"Missing commands: {', '.join(missing)}")
        return False
    print("All system dependencies are already installed.")
    return True


def hook_install(context: Dict[str, Any]) -> Dict[str, Any]:
    """Install missing system dependencies via platform package manager."""
    missing_cmds = _missing_commands()
    if not missing_cmds:
        print("All system dependencies already present — nothing to install.")
        return {"installed": True, "commands": [], "skipped": True}

    if IS_MACOS:
        # Ensure Homebrew first
        pkg_ensure_brew()
        pkg_update()

        # Map missing commands to Homebrew packages
        cmd_to_pkg = {
            "curl": "curl",
            "git": "git",
            "python3": "python@3.12",
            "pip3": "python@3.12",
            "make": "make",
            "gcc": "gcc",
            "jq": "jq",
            "openssl": "openssl@3",
            "unzip": "unzip",
        }
        pkg_set = set()
        for cmd in missing_cmds:
            if cmd in cmd_to_pkg:
                pkg_set.add(cmd_to_pkg[cmd])

        print(f"Installing via Homebrew: {', '.join(sorted(pkg_set))}")
        success = pkg_install(sorted(pkg_set))
    else:
        # Linux — use apt
        cmd_to_pkg = {
            "curl": "curl",
            "wget": "wget",
            "git": "git",
            "python3": "python3",
            "pip": "python3-pip",
            "make": "build-essential",
            "gcc": "build-essential",
            "jq": "jq",
            "openssl": "openssl",
            "unzip": "unzip",
        }
        pkg_set = set()
        for cmd in missing_cmds:
            if cmd in cmd_to_pkg:
                pkg_set.add(cmd_to_pkg[cmd])

        print(f"Installing via apt: {', '.join(sorted(pkg_set))}")
        success = pkg_install(sorted(pkg_set))

    return {
        "installed": success,
        "commands": missing_cmds,
        "skipped": not missing_cmds,
    }


def hook_verify(context: Dict[str, Any]) -> bool:
    """Verify all required commands are accessible."""
    for cmd in _get_required_commands():
        if not command_exists(cmd):
            raise RuntimeError(f"Command verification failed: {cmd} not found")
    print("All packages verified successfully.")
    return True


def hook_cleanup(context: Dict[str, Any]) -> None:
    """Clean up package cache."""
    pkg_clean()