"""
macOS platform adapters for Hermes Forge.

Provides Homebrew-based package management, launchctl service management,
and pfctl firewall management.
"""

import os
import subprocess
from typing import Any, Dict, List

# ─── Homebrew Package Manager ────────────────────────────────────────────────

BREW_PREFIXES = ["/opt/homebrew/bin/brew", "/usr/local/bin/brew", "/home/linuxbrew/.linuxbrew/bin/brew"]


class DarwinPackageManager:
    """macOS package management via Homebrew."""

    @staticmethod
    def _brew() -> str:
        """Find brew executable."""
        for prefix in BREW_PREFIXES:
            if os.path.isfile(prefix):
                return prefix
        return "brew"  # fallback — rely on PATH

    @staticmethod
    def ensure_brew() -> bool:
        """Install Homebrew if not present."""
        if _command_exists("brew"):
            return True
        print("Homebrew not found — installing...")
        install_cmd = '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
        try:
            subprocess.run(install_cmd, shell=True, check=True)
            return _command_exists("brew")
        except subprocess.CalledProcessError:
            return False

    @staticmethod
    def install(packages: List[str]) -> bool:
        """Install packages via brew."""
        brew = DarwinPackageManager._brew()
        try:
            # Filter out packages that don't have brew equivalents
            brew_packages = [p for p in packages if p not in
                             ("build-essential", "python3-pip", "iptables", "socat")]
            if not brew_packages:
                return True
            subprocess.run([brew, "install"] + brew_packages, check=True)
            return True
        except subprocess.CalledProcessError:
            return False

    @staticmethod
    def update() -> bool:
        """Run brew update."""
        brew = DarwinPackageManager._brew()
        try:
            subprocess.run([brew, "update"], check=True)
            return True
        except subprocess.CalledProcessError:
            return False

    @staticmethod
    def clean() -> bool:
        """Clean brew cache."""
        brew = DarwinPackageManager._brew()
        try:
            subprocess.run([brew, "cleanup"], check=True)
            return True
        except subprocess.CalledProcessError:
            return False


# ─── Launchd Service Manager ────────────────────────────────────────────────

class DarwinServiceManager:
    """macOS service management via launchctl."""

    @staticmethod
    def _plist_name(name: str) -> str:
        """Convert service name to plist filename."""
        return f"com.hermes.{name}.plist"

    @staticmethod
    def enable(name: str) -> bool:
        plist = DarwinServiceManager._plist_name(name)
        label = plist.replace(".plist", "")
        try:
            # Load the plist (enable = load on boot)
            subprocess.run(["launchctl", "load", "-w",
                            os.path.expanduser(f"~/Library/LaunchAgents/{plist}")],
                           capture_output=True, check=False)
            return True
        except Exception:
            return False

    @staticmethod
    def disable(name: str) -> bool:
        plist = DarwinServiceManager._plist_name(name)
        try:
            subprocess.run(["launchctl", "unload", "-w",
                            os.path.expanduser(f"~/Library/LaunchAgents/{plist}")],
                           capture_output=True, check=False)
            return True
        except Exception:
            return False

    @staticmethod
    def start(name: str) -> bool:
        plist = DarwinServiceManager._plist_name(name)
        label = plist.replace(".plist", "")
        try:
            # launchctl load starts the service
            subprocess.run(["launchctl", "load",
                            os.path.expanduser(f"~/Library/LaunchAgents/{plist}")],
                           capture_output=True, check=False)
            return True
        except Exception:
            return False

    @staticmethod
    def stop(name: str) -> bool:
        plist = DarwinServiceManager._plist_name(name)
        try:
            subprocess.run(["launchctl", "unload",
                            os.path.expanduser(f"~/Library/LaunchAgents/{plist}")],
                           capture_output=True, check=False)
            return True
        except Exception:
            return False

    @staticmethod
    def restart(name: str) -> bool:
        DarwinServiceManager.stop(name)
        DarwinServiceManager.start(name)
        return True

    @staticmethod
    def is_active(name: str) -> bool:
        plist = DarwinServiceManager._plist_name(name)
        label = plist.replace(".plist", "")
        try:
            result = subprocess.run(
                ["launchctl", "list", label],
                capture_output=True, text=True, check=False,
            )
            return result.returncode == 0 and label in result.stdout
        except Exception:
            return False

    @staticmethod
    def reload() -> None:
        """No-op — launchd doesn't need reloading like systemd."""
        pass

    @staticmethod
    def write_unit(name: str, content: str, user_home: str) -> str:
        """Write a launchd plist file."""
        launch_agents = os.path.join(user_home, "Library", "LaunchAgents")
        os.makedirs(launch_agents, exist_ok=True)
        path = os.path.join(launch_agents, content)  # content IS the plist name+content? No...
        # Actually, content is the plist content, name is the service name
        plist_name = DarwinServiceManager._plist_name(name)
        path = os.path.join(launch_agents, plist_name)
        with open(path, "w") as f:
            f.write(content)
        return path

    @staticmethod
    def remove_unit(name: str, user_home: str) -> bool:
        launch_agents = os.path.join(user_home, "Library", "LaunchAgents")
        path = os.path.join(launch_agents, DarwinServiceManager._plist_name(name))
        if os.path.isfile(path):
            os.remove(path)
            return True
        return False


# ─── Firewall (pfctl) ────────────────────────────────────────────────────────

class DarwinFirewall:
    """macOS firewall management via pfctl."""

    @staticmethod
    def apply() -> Dict[str, Any]:
        """Apply pf firewall rules to restrict to localhost only."""
        applied = []
        skipped = []

        if not _command_exists("pfctl"):
            skipped.append("pfctl (not available)")
            return {"applied": applied, "skipped": skipped}

        print("Applying pf firewall rules (macOS)...")
        anchor_content = """
# Hermes Forge — Restrict to localhost
block in log on en0 proto tcp from any to any port 8642
block in log on en0 proto tcp from any to any port 8643
block in log on en0 proto tcp from any to any port 18789
block in log on en0 proto tcp from any to any port 11434
block in log on en0 proto tcp from any to any port 3000
block in log on en0 proto tcp from any to any port 4000
block in log on en0 proto tcp from any to any port 7457
pass in quick on lo0 all
"""
        anchor_path = "/tmp/hermes-forge-pf.conf"
        try:
            with open(anchor_path, "w") as f:
                f.write(anchor_content)
            subprocess.run(["sudo", "pfctl", "-a", "hermes-forge", "-f", anchor_path],
                           capture_output=True, check=False)
            subprocess.run(["sudo", "pfctl", "-e"], capture_output=True, check=False)
            applied.append("pfctl rules")
        except Exception as e:
            skipped.append(f"pfctl apply failed: {e}")

        return {"applied": applied, "skipped": skipped}

    @staticmethod
    def restore() -> None:
        """Disable pf and flush rules."""
        try:
            subprocess.run(["sudo", "pfctl", "-a", "hermes-forge", "-F", "all"],
                           capture_output=True, check=False)
            subprocess.run(["sudo", "pfctl", "-d"], capture_output=True, check=False)
        except Exception:
            pass


def _command_exists(cmd: str) -> bool:
    try:
        subprocess.run(["which", cmd], capture_output=True, check=True)
        return True
    except subprocess.CalledProcessError:
        return False