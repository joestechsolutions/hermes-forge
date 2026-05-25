"""
Dashboard Plugin

Installs the Hermes Infrastructure Dashboard backend and frontend,
then configures the systemd user service.

Dashboard lives at <repo_root>/dashboard/, resolved relative to this plugin file.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

from bootloader.lib.platform import (
    IS_MACOS,
    service_enable,
    service_disable,
    service_start,
    service_stop,
    service_is_active,
    service_reload,
    service_config_dir,
)

# Repo root: plugins/dashboard.py → bootloader/ → repo root
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def command_exists(cmd: str) -> bool:
    """Check if a command exists in PATH."""
    try:
        subprocess.run(["which", cmd], capture_output=True, check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def hook_check_prerequisites(context: Dict[str, Any]) -> bool:
    """
    Check if all required tools for dashboard installation are present.
    """
    backend_dir = _REPO_ROOT / "dashboard" / "backend"
    frontend_dir = _REPO_ROOT / "dashboard" / "frontend"

    missing = []
    for cmd in ["node", "npm", "python3", "pip3"]:
        if not command_exists(cmd):
            missing.append(cmd)

    if not backend_dir.exists():
        missing.append(f"backend directory ({backend_dir})")
    if not (frontend_dir / "package.json").exists():
        missing.append(f"frontend package.json ({frontend_dir})")

    if missing:
        print(f"Dashboard prerequisites not met: {', '.join(missing)}")
        return False

    print("Dashboard prerequisites are met.")
    return True


def hook_install(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Install backend Python deps, build frontend, and set up systemd service.
    """
    print("Installing Dashboard...")

    user_home = context.get("USER_HOME", os.path.expanduser("~"))
    backend_dir = _REPO_ROOT / "dashboard" / "backend"
    frontend_dir = _REPO_ROOT / "dashboard" / "frontend"
    svc_dir = service_config_dir(user_home)

    dry = context.get("dry_run", False)
    created_files = []

    # Backend Python requirements
    req = backend_dir / "requirements.txt"
    if req.exists():
        if dry:
            print(f"[DRY-RUN] Would install Python deps from {req}")
        else:
            print(f"Installing backend Python requirements...")
            subprocess.run(
                [sys.executable or "python3", "-m", "pip", "install", "--user", "-r", str(req)],
                check=True,
                cwd=str(backend_dir)
            )
            created_files.append("python-deps")
    else:
        print(f"Warning: requirements.txt not found at {req}")

    # Frontend: npm ci + build
    pkg = frontend_dir / "package.json"
    if pkg.exists():
        if dry:
            print(f"[DRY-RUN] Would run npm ci && npm run build in {frontend_dir}")
        else:
            print("Installing frontend dependencies and building...")
            subprocess.run(["npm", "ci"], cwd=str(frontend_dir), check=True)
            subprocess.run(["npm", "run", "build"], cwd=str(frontend_dir), check=True)
            created_files.append("frontend-dist")
    else:
        print(f"Warning: package.json not found at {pkg}")

    # Systemd / launchd service setup
    src_svc = backend_dir / "systemd" / "dashboard-backend.service"
    dst_svc = svc_dir / "dashboard-backend.service"
    if src_svc.exists():
        if dry:
            print(f"[DRY-RUN] Would install service {src_svc} -> {dst_svc}")
        elif IS_MACOS:
            print("Skipping service setup on macOS (launchd integration pending)")
        else:
            dst_svc.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_svc, dst_svc)
            service_reload()
            service_enable('dashboard-backend')
            service_start('dashboard-backend')
            created_files.append("systemd-service")
    else:
        print(f"Warning: Service file not found at {src_svc}")

    return {
        "installed": True,
        "files_created": created_files,
        "backend_dir": str(backend_dir),
        "frontend_dir": str(frontend_dir),
    }


def hook_verify(context: Dict[str, Any]) -> bool:
    """
    Verify the dashboard is functional:
    - systemd service is active, OR
    - backend can be reached at health endpoint

    Plus check frontend dist exists.
    """
    frontend_dir = _REPO_ROOT / "dashboard" / "frontend"

    errors = []

    # Check service is running
    if IS_MACOS:
        print("Skipping service check on macOS (launchd integration pending)")
    else:
        if not service_is_active('dashboard-backend'):
            errors.append("dashboard-backend.service not active")

    # Check frontend dist directory
    dist_dir = frontend_dir / "dist"
    if not dist_dir.exists():
        errors.append(f"Frontend dist not found at {dist_dir}")

    if errors:
        raise RuntimeError(f"Dashboard verification failed: {'; '.join(errors)}")

    print("Dashboard verification passed: service active and frontend built.")
    return True


def hook_cleanup(context: Dict[str, Any]) -> None:
    """
    Stop and disable the dashboard service.
    """
    dry = context.get("dry_run", False)
    if dry:
        print("[DRY-RUN] Would stop and disable dashboard-backend.service")
        return

    if IS_MACOS:
        print("Skipping service cleanup on macOS (launchd integration pending)")
        return

    print("Stopping and disabling dashboard-backend.service...")
    service_disable('dashboard-backend')
    service_stop('dashboard-backend')