"""
Security Hardening Plugin

Sets restrictive file permissions on user dotdirs and applies
network-level hardening (firewall) via the platform abstraction layer.
"""

import os
import stat
from typing import Any, Dict

from bootloader.lib.platform import (
    IS_MACOS,
    IS_LINUX,
    IS_WSL,
    firewall_apply_hardening,
    firewall_restore,
    get_protected_dirs,
    get_protected_files,
    system_data_dir,
)


def _chmod_recursive(path: str, mode: int) -> None:
    """Recursively set directory permissions on files."""
    for root, dirs, files in os.walk(path):
        os.chmod(root, mode)
        for d in dirs:
            os.chmod(os.path.join(root, d), mode)
        for fname in files:
            fpath = os.path.join(root, fname)
            # For files, remove execute bit
            current = os.stat(fpath).st_mode
            os.chmod(fpath, current & 0o777 & ~0o111)


def hook_check_prerequisites(context: Dict[str, Any]) -> bool:
    """
    Always returns True — install applies hardening if needed.
    """
    user_home = context.get("USER_HOME", os.path.expanduser("~"))
    hermes = os.path.join(user_home, ".hermes")
    if not os.path.isdir(hermes):
        print("Hermes directory doesn't exist yet — will be created during install.")
    else:
        try:
            perms = os.stat(hermes).st_mode & 0o777
            if perms == 0o700:
                print("Hermes directory is already secured (mode 700).")
            else:
                print(f"Hermes directory has mode {oct(perms)} — will apply hardening.")
        except Exception as e:
            print(f"Could not check permissions: {e} — will apply hardening.")
    return True


def hook_install(context: Dict[str, Any]) -> Dict[str, Any]:
    print("Applying security hardening...")

    user_home = context.get("USER_HOME", os.path.expanduser("~"))
    applied = []
    skipped = []

    # Set restrictive permissions on directories (mode 700)
    for dir_path in get_protected_dirs(user_home):
        if not os.path.isdir(dir_path):
            skipped.append(f"{os.path.relpath(dir_path, user_home)} (not found)")
            continue
        _chmod_recursive(dir_path, 0o700)
        applied.append(os.path.relpath(dir_path, user_home))

    # Set restrictive permissions on config files (mode 600)
    for file_path in get_protected_files(user_home):
        if not os.path.isfile(file_path):
            skipped.append(f"{os.path.relpath(file_path, user_home)} (not found)")
            continue
        os.chmod(file_path, 0o600)
        applied.append(os.path.relpath(file_path, user_home))

    # Network hardening — delegates to platform layer
    # (iptables on Linux, pfctl on macOS, skipped automatically on WSL)
    result = firewall_apply_hardening()
    applied.extend(result.get("applied", []))
    skipped.extend(result.get("skipped", []))

    print(f"Hardening applied: {applied}")
    if skipped:
        print(f"Skipped: {skipped}")
    return {"installed": True, "applied": applied, "skipped": skipped}


def hook_verify(context: Dict[str, Any]) -> bool:
    user_home = context.get("USER_HOME", os.path.expanduser("~"))
    errors = []

    for dir_path in get_protected_dirs(user_home):
        if not os.path.isdir(dir_path):
            continue
        perms = os.stat(dir_path).st_mode & 0o777
        if perms != 0o700:
            errors.append(f"{os.path.relpath(dir_path, user_home)} has mode {oct(perms)}, expected 0o700")

    for file_path in get_protected_files(user_home):
        if not os.path.isfile(file_path):
            continue
        perms = os.stat(file_path).st_mode & 0o777
        if perms != 0o600:
            errors.append(f"{os.path.relpath(file_path, user_home)} has mode {oct(perms)}, expected 0o600")

    if errors:
        raise RuntimeError(f"Security hardening verification failed: {'; '.join(errors)}")
    print("Security hardening verified successfully.")
    return True


def hook_cleanup(context: Dict[str, Any]) -> None:
    # Cannot really undo file permissions without knowing originals
    print("Security hardening cleanup — file permissions are persistent.")
    # Restore firewall to permissive state — delegates to platform layer
    firewall_restore()
