"""
Linux platform adapters for Hermes Forge.

Provides apt-based package management, systemctl service management,
and iptables firewall management.
"""

import os
import subprocess
from typing import Any, Dict, List


# ─── Package Manager (apt) ───────────────────────────────────────────────────

class LinuxPackageManager:
    """Linux package management via apt-get."""

    @staticmethod
    def install(packages: List[str]) -> bool:
        """Install packages via apt-get."""
        try:
            subprocess.run(["apt-get", "update", "-qq"], check=True)
            subprocess.run(["apt-get", "install", "-y", "-qq"] + packages, check=True)
            return True
        except subprocess.CalledProcessError:
            return False

    @staticmethod
    def update() -> bool:
        """Run apt-get update."""
        try:
            subprocess.run(["apt-get", "update", "-qq"], check=True)
            return True
        except subprocess.CalledProcessError:
            return False

    @staticmethod
    def clean() -> bool:
        """Clean apt cache."""
        try:
            subprocess.run(["apt-get", "clean"], check=True)
            return True
        except subprocess.CalledProcessError:
            return False


# ─── Service Manager (systemd) ───────────────────────────────────────────────

class LinuxServiceManager:
    """Linux service management via systemctl --user."""

    USER_HOME: str = os.path.expanduser("~")

    @staticmethod
    def _systemctl(args: List[str]) -> bool:
        try:
            subprocess.run(["systemctl", "--user"] + args, capture_output=True, check=True)
            return True
        except subprocess.CalledProcessError:
            return False

    @staticmethod
    def enable(name: str) -> bool:
        return LinuxServiceManager._systemctl(["enable", name])

    @staticmethod
    def disable(name: str) -> bool:
        return LinuxServiceManager._systemctl(["disable", name])

    @staticmethod
    def start(name: str) -> bool:
        return LinuxServiceManager._systemctl(["start", name])

    @staticmethod
    def stop(name: str) -> bool:
        return LinuxServiceManager._systemctl(["stop", name])

    @staticmethod
    def restart(name: str) -> bool:
        return LinuxServiceManager._systemctl(["restart", name])

    @staticmethod
    def is_active(name: str) -> bool:
        try:
            result = subprocess.run(
                ["systemctl", "--user", "is-active", name],
                capture_output=True, text=True, check=False,
            )
            return result.stdout.strip() == "active"
        except Exception:
            return False

    @staticmethod
    def reload() -> None:
        subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True)

    @staticmethod
    def write_unit(name: str, content: str, user_home: str) -> str:
        """Write a systemd unit file."""
        unit_dir = os.path.join(user_home, ".config", "systemd", "user")
        os.makedirs(unit_dir, exist_ok=True)
        path = os.path.join(unit_dir, name)
        with open(path, "w") as f:
            f.write(content)
        LinuxServiceManager.reload()
        return path

    @staticmethod
    def remove_unit(name: str, user_home: str) -> bool:
        unit_dir = os.path.join(user_home, ".config", "systemd", "user")
        path = os.path.join(unit_dir, name)
        if os.path.isfile(path):
            os.remove(path)
            LinuxServiceManager.reload()
            return True
        return False


# ─── Firewall (iptables) ─────────────────────────────────────────────────────

class LinuxFirewall:
    """Linux firewall management via iptables."""

    @staticmethod
    def apply() -> Dict[str, Any]:
        """Apply iptables hardening rules. Safe ordering: allow SSH before DROP."""
        applied = []
        skipped = []

        # Check if we're on WSL — skip iptables there
        try:
            with open("/proc/version") as f:
                if "microsoft" in f.read().lower():
                    skipped.append("iptables (WSL2)")
                    return {"applied": applied, "skipped": skipped}
        except Exception:
            pass

        if not _command_exists("iptables"):
            skipped.append("iptables (not available)")
            return {"applied": applied, "skipped": skipped}

        print("Applying iptables rules...")
        rules = [
            ["iptables", "-F"],
            ["iptables", "-X"],
            ["iptables", "-A", "INPUT", "-m", "state", "--state", "ESTABLISHED,RELATED", "-j", "ACCEPT"],
            ["iptables", "-A", "INPUT", "-p", "tcp", "--dport", "22", "-j", "ACCEPT"],
            ["iptables", "-A", "INPUT", "-i", "lo", "-j", "ACCEPT"],
            ["iptables", "-A", "INPUT", "-s", "127.0.0.0/8", "-j", "ACCEPT"],
            ["iptables", "-P", "INPUT", "DROP"],
        ]
        for rule in rules:
            try:
                subprocess.run(rule, capture_output=True, check=True)
            except subprocess.CalledProcessError:
                pass
        applied.append("iptables rules")
        return {"applied": applied, "skipped": skipped}

    @staticmethod
    def restore() -> None:
        """Restore iptables to permissive state."""
        subprocess.run(["iptables", "-P", "INPUT", "ACCEPT"], capture_output=True)


def _command_exists(cmd: str) -> bool:
    try:
        subprocess.run(["which", cmd], capture_output=True, check=True)
        return True
    except subprocess.CalledProcessError:
        return False