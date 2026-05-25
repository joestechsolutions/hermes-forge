"""
Open Design Plugin

Clones and installs the Open Design web app.
Supports Linux (/srv/ai-stack) and macOS (/usr/local/var/ai-stack).
"""

import os
import subprocess
from typing import Any, Dict

from bootloader.lib.platform import system_data_dir


OPEN_DESIGN_REPO = "https://github.com/nousresearch/open-design.git"


def _install_dir(context: Dict[str, Any]) -> str:
    user_home = context.get("USER_HOME", os.path.expanduser("~"))
    return os.path.join(system_data_dir(user_home), "open-design")


def hook_check_prerequisites(context: Dict[str, Any]) -> bool:
    install_path = _install_dir(context)
    if os.path.isdir(install_path):
        print(f"Open Design already at {install_path}")
    print("Open Design can be installed (or is already present).")
    return True


def hook_install(context: Dict[str, Any]) -> Dict[str, Any]:
    print("Installing Open Design...")

    install_path = _install_dir(context)

    if not os.path.isdir(install_path):
        print(f"Cloning {OPEN_DESIGN_REPO} into {install_path}")
        os.makedirs(install_path, exist_ok=True)
        subprocess.run(["git", "clone", OPEN_DESIGN_REPO, install_path], check=True)
    elif os.path.isdir(os.path.join(install_path, ".git")):
        print(f"Open Design dir exists, pulling latest...")
        subprocess.run(["git", "-C", install_path, "pull"], check=True)
    else:
        print(f"Open Design dir exists but is not a git repo — skipping git update.")

    print("Installing Node dependencies with pnpm...")
    subprocess.run(
        ["pnpm", "--dir", install_path, "install"],
        check=True,
        capture_output=True,
    )

    node_modules = os.path.join(install_path, "node_modules")
    return {
        "installed": True,
        "install_path": install_path,
        "node_modules_present": os.path.isdir(node_modules),
        "skipped": False,
    }


def hook_verify(context: Dict[str, Any]) -> bool:
    install_path = _install_dir(context)
    if not os.path.isdir(install_path):
        raise RuntimeError(f"Open Design directory not found at {install_path}")
    node_modules = os.path.join(install_path, "node_modules")
    if os.path.isdir(node_modules):
        print(f"Open Design node_modules verified at {node_modules}")
    else:
        print(f"Open Design directory exists at {install_path} (service-managed — node_modules may be installed on demand)")
    return True


def hook_cleanup(context: Dict[str, Any]) -> None:
    pass