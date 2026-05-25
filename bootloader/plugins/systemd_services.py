"""
Service Installation Plugin

Creates and manages service unit files for Hermes Gateway, OpenClaw Gateway,
and Open Design services. Supports systemd (Linux) and launchd (macOS) via
the bootloader.lib.platform abstraction layer.
"""

import os
from typing import Any, Dict

from bootloader.lib.platform import (
    IS_MACOS,
    service_enable,
    service_disable,
    service_start,
    service_stop,
    service_restart,
    service_is_active,
    service_reload,
    write_service_unit,
    remove_service_unit,
    service_config_dir,
    system_data_dir,
)
from bootloader.lib.platform.plist_gen import generate_plist


# ─── Service definitions ────────────────────────────────────────────────────
# Data-only — content is generated per-platform below.

SERVICE_DEFINITIONS = [
    {
        "id": "hermes-gateway",
        "description": "Hermes Gateway Service",
        "linux_unit_name": "hermes-gateway.service",
        "macos_unit_name": "hermes-gateway",
        "linux_work_dir": "%h/.hermes/hermes-agent",
        "macos_work_dir_rel_home": ".hermes/hermes-agent",
        "linux_exec": "%h/.hermes/hermes-agent/venv/bin/python -m hermes_agent server",
        "linux_path": (
            "%h/.hermes/hermes-agent/venv/bin:"
            "%h/.local/bin:/usr/local/bin:/usr/bin:/bin"
        ),
        "macos_venv_python": ".hermes/hermes-agent/venv/bin/python",
        "macos_module_args": "-m hermes_agent server",
    },
    {
        "id": "openclaw-gateway",
        "description": "OpenClaw Gateway Service",
        "linux_unit_name": "openclaw-gateway.service",
        "macos_unit_name": "openclaw-gateway",
        "linux_work_dir": "%h/.openclaw/hermes-openclaw",
        "macos_work_dir_rel_home": ".openclaw/hermes-openclaw",
        "linux_exec": "%h/.openclaw/hermes-openclaw/venv/bin/python -m openclaw",
        "linux_path": (
            "%h/.openclaw/hermes-openclaw/venv/bin:"
            "%h/.local/bin:/usr/local/bin:/usr/bin:/bin"
        ),
        "macos_venv_python": ".openclaw/hermes-openclaw/venv/bin/python",
        "macos_module_args": "-m openclaw",
    },
    {
        "id": "open-design",
        "description": "Open Design Web UI",
        "linux_unit_name": "open-design.service",
        "macos_unit_name": "open-design",
        "linux_work_dir": "/srv/ai-stack/open-design",
        "linux_exec": "/usr/local/bin/pnpm run dev",
        "linux_path": "/usr/local/bin:/usr/bin:/bin",
        # On macOS the working directory is system_data_dir/open-design
        "macos_binary": "pnpm",
        "macos_module_args": "run dev",
        "uses_venv": False,
    },
]


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _service_names(svc: Dict[str, Any]) -> str:
    """Return the unit/service name for the current platform."""
    return svc["macos_unit_name"] if IS_MACOS else svc["linux_unit_name"]


def _linux_unit_content(svc: Dict[str, Any]) -> str:
    """Build systemd unit file content for a service definition."""
    return f"""[Unit]
Description={svc["description"]}
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory={svc["linux_work_dir"]}
Environment=PATH={svc["linux_path"]}
ExecStart={svc["linux_exec"]}
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
"""


def _macos_plist_content(svc: Dict[str, Any], user_home: str) -> str:
    """Build launchd plist XML for a service definition using generate_plist."""
    label = f"com.hermes.{svc['id']}"

    if svc["id"] == "open-design":
        sdd = system_data_dir(user_home)
        work_dir = os.path.join(sdd, "open-design")
        command = f"pnpm run dev"
        env = {
            "PATH": "/usr/local/bin:/usr/bin:/bin",
        }
    else:
        work_dir = os.path.join(user_home, svc["macos_work_dir_rel_home"])
        venv_python = os.path.join(user_home, svc["macos_venv_python"])
        venv_dir = os.path.dirname(venv_python)
        command = f"{venv_python} {svc['macos_module_args']}"
        env = {
            "PATH": f"{venv_dir}:{os.path.join(user_home, '.local/bin')}:/usr/local/bin:/usr/bin:/bin",
        }

    return generate_plist(
        label=label,
        command=command,
        working_directory=work_dir,
        environment=env,
        keep_alive=True,
        run_at_load=True,
        standard_out_path=f"/tmp/{svc['id']}.log",
        standard_err_path=f"/tmp/{svc['id']}-err.log",
        restart_interval=10,
    )


def _get_user_home(context: Dict[str, Any]) -> str:
    return context.get("USER_HOME", os.path.expanduser("~"))


# ─── Hooks ────────────────────────────────────────────────────────────────────


def hook_check_prerequisites(context: Dict[str, Any]) -> bool:
    """Check which service files already exist."""
    user_home = _get_user_home(context)
    cfg_dir = service_config_dir(user_home)
    platform_label = "launchd" if IS_MACOS else "systemd"

    missing = []
    for svc in SERVICE_DEFINITIONS:
        name = _service_names(svc)
        if IS_MACOS:
            from bootloader.lib.platform.darwin import DarwinServiceManager
            path = os.path.join(cfg_dir, DarwinServiceManager._plist_name(name))
        else:
            path = os.path.join(cfg_dir, name)
        if not os.path.isfile(path):
            missing.append(name)

    if not missing:
        print(f"All {platform_label} service files already exist.")
    else:
        print(f"Installing {platform_label} services: {', '.join(missing)}")
    return True


def hook_install(context: Dict[str, Any]) -> Dict[str, Any]:
    """Write service unit/plist files and enable them."""
    user_home = _get_user_home(context)
    platform_label = "launchd" if IS_MACOS else "systemd"

    print(f"Installing {platform_label} service files...")

    installed_units = []
    for svc in SERVICE_DEFINITIONS:
        name = _service_names(svc)

        if IS_MACOS:
            content = _macos_plist_content(svc, user_home)
        else:
            content = _linux_unit_content(svc)

        path = write_service_unit(name, content, user_home)
        installed_units.append(name)
        print(f"  Wrote {name} -> {path}")

    # Enable all services
    print(f"Enabling all services...")
    for name in installed_units:
        ok = service_enable(name)
        status = "OK" if ok else "FAILED"
        print(f"  enable {name} ... {status}")

    return {
        "installed": True,
        "unit_dir": service_config_dir(user_home),
        "units": installed_units,
    }


def hook_verify(context: Dict[str, Any]) -> bool:
    """Verify that service files exist and are registered."""
    user_home = _get_user_home(context)
    cfg_dir = service_config_dir(user_home)
    errors = []

    for svc in SERVICE_DEFINITIONS:
        name = _service_names(svc)

        if IS_MACOS:
            from bootloader.lib.platform.darwin import DarwinServiceManager
            path = os.path.join(cfg_dir, DarwinServiceManager._plist_name(name))
            label = f"com.hermes.{svc['id']}"
            exists = os.path.isfile(path)
            if not exists:
                errors.append(f"{name} plist not found at {path}")
                continue
            # Verify via launchctl list
            import subprocess
            result = subprocess.run(
                ["launchctl", "list", label],
                capture_output=True, text=True, check=False,
            )
            if result.returncode != 0 and "could not find" in result.stderr.lower():
                errors.append(f"{name} (label {label}) not registered with launchd")
        else:
            path = os.path.join(cfg_dir, name)
            if not os.path.isfile(path):
                errors.append(f"{name} not found at {path}")
                continue
            # Verify via systemctl cat
            import subprocess
            result = subprocess.run(
                ["systemctl", "--user", "cat", name],
                capture_output=True, check=False,
            )
            if result.returncode != 0:
                errors.append(f"{name} failed systemctl cat check")

    if errors:
        raise RuntimeError(
            f"Service verification failed on {'macOS' if IS_MACOS else 'Linux'}: "
            f"{'; '.join(errors)}"
        )
    print(f"All service files verified ({'launchd' if IS_MACOS else 'systemd'}).")
    return True


def hook_cleanup(context: Dict[str, Any]) -> None:
    """Disable and remove all service files."""
    user_home = _get_user_home(context)

    print("Cleaning up services...")
    for svc in SERVICE_DEFINITIONS:
        name = _service_names(svc)
        service_disable(name)
        remove_service_unit(name, user_home)
        print(f"  Removed {name}")