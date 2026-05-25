"""
Platform detection and abstraction layer.

Usage:
  from . import platform
  pkg_manager.install("curl")
  service_manager.enable("hermes-gateway")
  print(platform.data_dir)  # ~/Library/... on macOS, /srv/ on Linux

Plugins should NEVER call apt-get, brew, systemctl, or launchctl directly.
Always go through this layer.
"""

import os
import platform as _stdlib_platform
from typing import Any, Dict, List, Optional, Tuple

# ─── Detect current OS ───────────────────────────────────────────────────────

SYSTEM = _stdlib_platform.system().lower()  # "linux" | "darwin" | "windows"
IS_LINUX = SYSTEM == "linux"
IS_MACOS = SYSTEM == "darwin"
IS_WSL = False
IS_ROOT = os.geteuid() == 0 if hasattr(os, "geteuid") else False

if IS_LINUX:
    try:
        with open("/proc/version") as _f:
            IS_WSL = "microsoft" in _f.read().lower()
    except Exception:
        pass

CURRENT_OS = "darwin" if IS_MACOS else "windows" if SYSTEM == "windows" else "linux"

# ─── Path helpers ────────────────────────────────────────────────────────────

def _ensure_dir(path: str, mode: int = 0o755) -> str:
    os.makedirs(path, mode=mode, exist_ok=True)
    return path


def system_data_dir(user_home: str) -> str:
    """System-level data directory (usually needs sudo to create)."""
    if IS_MACOS:
        return "/usr/local/var/ai-stack"  # macOS: no /srv/
    return "/srv/ai-stack"


def user_data_dir(user_home: str) -> str:
    """User-level data directory for logs, state, etc."""
    if IS_MACOS:
        return _ensure_dir(os.path.join(user_home, "Library", "Application Support", "ai-stack"))
    return _ensure_dir(os.path.join(user_home, ".hermes"))


def service_config_dir(user_home: str) -> str:
    """Directory for service/daemon config files."""
    if IS_MACOS:
        return _ensure_dir(os.path.join(user_home, "Library", "LaunchAgents"))
    return _ensure_dir(os.path.join(user_home, ".config", "systemd", "user"))


def binary_dir(user_home: str) -> str:
    """User bin directory."""
    if IS_MACOS:
        return _ensure_dir(os.path.join(user_home, "Library", "Application Support", "hermes", "bin"))
    return _ensure_dir(os.path.join(user_home, ".hermes", "node", "bin"))


# ─── Service manager abstraction ─────────────────────────────────────────────

_service_backend: Optional[Any] = None


def _get_service_backend():
    global _service_backend
    if _service_backend is not None:
        return _service_backend
    if IS_MACOS:
        from .darwin import DarwinServiceManager
        _service_backend = DarwinServiceManager()
    else:
        from .linux import LinuxServiceManager
        _service_backend = LinuxServiceManager()
    return _service_backend


def service_enable(name: str) -> bool:
    return _get_service_backend().enable(name)


def service_disable(name: str) -> bool:
    return _get_service_backend().disable(name)


def service_start(name: str) -> bool:
    return _get_service_backend().start(name)


def service_stop(name: str) -> bool:
    return _get_service_backend().stop(name)


def service_restart(name: str) -> bool:
    return _get_service_backend().restart(name)


def service_is_active(name: str) -> bool:
    return _get_service_backend().is_active(name)


def service_reload() -> None:
    _get_service_backend().reload()


def write_service_unit(name: str, content: str, user_home: str) -> str:
    """Write a service unit/plist file and return the path."""
    return _get_service_backend().write_unit(name, content, user_home)


def remove_service_unit(name: str, user_home: str) -> bool:
    return _get_service_backend().remove_unit(name, user_home)


# ─── Package manager abstraction ─────────────────────────────────────────────

_pkg_backend: Optional[Any] = None


def _get_pkg_backend():
    global _pkg_backend
    if _pkg_backend is not None:
        return _pkg_backend
    if IS_MACOS:
        from .darwin import DarwinPackageManager
        _pkg_backend = DarwinPackageManager()
    else:
        from .linux import LinuxPackageManager
        _pkg_backend = LinuxPackageManager()
    return _pkg_backend


def pkg_install(packages: List[str]) -> bool:
    return _get_pkg_backend().install(packages)


def pkg_update() -> bool:
    return _get_pkg_backend().update()


def pkg_clean() -> bool:
    return _get_pkg_backend().clean()


def pkg_ensure_brew() -> bool:
    """Ensure Homebrew is installed (macOS only). No-op on Linux."""
    if IS_MACOS:
        from .darwin import DarwinPackageManager
        return DarwinPackageManager().ensure_brew()
    return True


# ─── Firewall abstraction ────────────────────────────────────────────────────

def firewall_apply_hardening() -> Dict[str, Any]:
    """Apply network hardening rules. Returns {'applied': [...], 'skipped': [...]}."""
    if IS_MACOS:
        from .darwin import DarwinFirewall
        return DarwinFirewall().apply()
    else:
        from .linux import LinuxFirewall
        return LinuxFirewall().apply()


def firewall_restore() -> None:
    """Restore firewall to permissive state."""
    if IS_MACOS:
        from .darwin import DarwinFirewall
        DarwinFirewall().restore()
    else:
        from .linux import LinuxFirewall
        LinuxFirewall().restore()


# ─── Conventions ─────────────────────────────────────────────────────────────

# Commands that should always be available on the target platform
REQUIRED_COMMANDS_LINUX = [
    "curl", "wget", "git", "python3", "pip", "make", "gcc",
    "iptables", "jq", "openssl", "socat", "unzip", "systemctl",
]

REQUIRED_COMMANDS_MACOS = [
    "curl", "git", "python3", "pip3", "make",
    "jq", "openssl", "unzip",
]

# Paths that get special permissions on Linux vs macOS
PROTECTED_DIRS = [
    ".hermes",
    ".hermes/sessions",
    ".hermes/logs",
    ".hermes/memories",
    ".hermes/checkpoints",
    ".openclaw",
    ".openclaw/workspace",
    ".mempalace",
]

PROTECTED_FILES = [
    ".hermes/config.yaml",
    ".hermes/.env",
    ".openclaw/config.yaml",
]


def get_protected_dirs(user_home: str) -> List[str]:
    return [os.path.join(user_home, d) for d in PROTECTED_DIRS]


def get_protected_files(user_home: str) -> List[str]:
    return [os.path.join(user_home, f) for f in PROTECTED_FILES]