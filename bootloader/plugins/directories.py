"""
Directories Plugin

Creates the required directory structure for the AI platform.
"""

import os
import subprocess
from typing import Any, Dict, List

from bootloader.lib.platform import IS_MACOS, system_data_dir


def hook_check_prerequisites(context: Dict[str, Any]) -> bool:
    """
    Check that the filesystem is writable enough to create directories.

    The bootloader's job is to CREATE directories, so we only check the
    parent directories exist and are writable, not that target dirs exist.
    """
    user_home = context.get("USER_HOME", os.path.expanduser("~"))
    parent_dirs = [
        user_home,
        f"{user_home}/.config",
        f"{user_home}/.config/systemd",
    ]

    missing = [d for d in parent_dirs if not os.path.isdir(d)]

    if missing:
        print(f"Parent directories missing: {', '.join(missing)}")
        return False

    # Check writability of home
    if not os.access(user_home, os.W_OK):
        print(f"Home directory {user_home} is not writable")
        return False

    print("Filesystem is writable — can create directories as needed.")
    return True


def hook_install(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create all required directories with proper permissions.

    Returns:
        Dict with installation results, including list of created directories.
    """
    print("Creating directory structure...")

    user_home = context.get("USER_HOME", os.path.expanduser("~"))

    directories = [
        (f"{user_home}/.hermes", 0o700),
        (f"{user_home}/.hermes/logs", 0o700),
        (f"{user_home}/.hermes/sessions", 0o700),
        (f"{user_home}/.hermes/memories", 0o700),
        (f"{user_home}/.hermes/checkpoints", 0o700),
        (f"{user_home}/.openclaw", 0o700),
        (f"{user_home}/.openclaw/workspace", 0o700),
        (f"{user_home}/.mempalace", 0o700),
        (system_data_dir(user_home), 0o755),  # system dir, accessible
        (f"{user_home}/.config/systemd/user", 0o755),
    ]

    created = []
    for dir_path, perms in directories:
        if not os.path.exists(dir_path):
            # For system directories, might need sudo (macOS uses /usr/local/var/ — no sudo needed)
            if dir_path.startswith("/srv") or dir_path.startswith("/etc"):
                subprocess.run(["sudo", "mkdir", "-p", dir_path], check=True)
                subprocess.run(["sudo", "chmod", oct(perms)[2:], dir_path], check=True)
            else:
                os.makedirs(dir_path, mode=perms, exist_ok=True)
            created.append(dir_path)
            print(f"Created: {dir_path} (perms: {oct(perms)})")
        else:
            print(f"Exists: {dir_path}")

    print("Directory structure created successfully.")
    return {
        "installed": True,
        "created_directories": created,
        "total_directories": len(directories)
    }


def hook_verify(context: Dict[str, Any]) -> bool:
    """
    Verify all required directories exist with correct permissions.

    Returns True if verification passes, raises RuntimeError otherwise.
    """
    user_home = context.get("USER_HOME", os.path.expanduser("~"))
    dirs_and_perms = [
        (f"{user_home}/.hermes", 0o700),
        (f"{user_home}/.hermes/logs", 0o700),
        (f"{user_home}/.hermes/sessions", 0o700),
        (f"{user_home}/.hermes/memories", 0o700),
        (f"{user_home}/.hermes/checkpoints", 0o700),
        (f"{user_home}/.openclaw", 0o700),
        (f"{user_home}/.openclaw/workspace", 0o700),
        (f"{user_home}/.mempalace", 0o700),
        (system_data_dir(user_home), 0o755),
        (f"{user_home}/.config/systemd/user", 0o755),
    ]

    errors = []
    for dir_path, expected_perms in dirs_and_perms:
        if not os.path.isdir(dir_path):
            errors.append(f"{dir_path} does not exist")
            continue

        try:
            # Get actual permissions (stat().st_mode & 0o777)
            actual_perms = os.stat(dir_path).st_mode & 0o777
            if actual_perms != expected_perms:
                errors.append(f"{dir_path} has perms {oct(actual_perms)}, expected {oct(expected_perms)}")
        except Exception as e:
            errors.append(f"{dir_path} permission check error: {e}")

    if errors:
        raise RuntimeError(f"Directory verification failed: {'; '.join(errors)}")

    print("All directories verified successfully.")
    return True


def hook_cleanup(context: Dict[str, Any]) -> None:
    """
    No cleanup needed for directories.
    """
    pass
