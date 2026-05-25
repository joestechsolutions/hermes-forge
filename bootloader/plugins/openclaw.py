"""
OpenClaw Plugin

Clones hermes-openclaw repository and installs dependencies.
"""

import os
import subprocess
import venv
from typing import Any, Dict


OPENCLAW_REPO = "https://github.com/nousresearch/hermes-openclaw.git"


def _command_exists(cmd: str) -> bool:
    try:
        subprocess.run(["which", cmd], capture_output=True, check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def hook_check_prerequisites(context: Dict[str, Any]) -> bool:
    user_home = context.get("USER_HOME", os.path.expanduser("~"))
    oc_dir = os.path.join(user_home, ".openclaw", "hermes-openclaw")
    oc_binary = os.path.join(user_home, ".hermes", "node", "bin", "openclaw")
    if os.path.isdir(oc_dir):
        print(f"OpenClaw already exists at {oc_dir}")
    if os.path.isfile(oc_binary) and os.access(oc_binary, os.X_OK):
        print(f"OpenClaw binary found at {oc_binary}")
    print("OpenClaw can be installed (or is already present).")
    return True


def hook_install(context: Dict[str, Any]) -> Dict[str, Any]:
    user_home = context.get("USER_HOME", os.path.expanduser("~"))
    openclaw_binary = os.path.join(user_home, ".hermes", "node", "bin", "openclaw")

    # ── BINARY CHECK: If openclaw is already installed as a node binary, skip ──
    if os.path.isfile(openclaw_binary) and os.access(openclaw_binary, os.X_OK):
        try:
            result = subprocess.run([openclaw_binary, "--version"], capture_output=True, text=True, timeout=10)
            version = result.stdout.strip() or result.stderr.strip() or "unknown"
            print(f"OpenClaw binary found at {openclaw_binary} (version: {version}) — skipping install.")
        except Exception as e:
            print(f"OpenClaw binary found at {openclaw_binary} (version check failed: {e}) — skipping install.")
        return {"installed": True, "skipped": True, "reason": "binary_exists", "binary_path": openclaw_binary}

    print("Installing OpenClaw...")

    openclaw_home = os.path.join(user_home, ".openclaw")
    oc_dir = os.path.join(openclaw_home, "hermes-openclaw")
    venv_dir = os.path.join(oc_dir, "venv")

    os.makedirs(openclaw_home, exist_ok=True)

    if not os.path.isdir(oc_dir):
        print(f"Cloning {OPENCLAW_REPO} into {oc_dir}")
        result = subprocess.run(
            ["git", "clone", "--depth", "1", OPENCLAW_REPO, oc_dir],
            capture_output=True,
        )
        if result.returncode != 0:
            print(f"Warning: Could not clone OpenClaw repo: {result.stderr.decode().strip()}")
            print("OpenClaw will not be installed.")
            return {"installed": False, "skipped": True, "reason": "repo_not_found"}
    elif os.path.isdir(os.path.join(oc_dir, ".git")):
        print(f"OpenClaw dir exists, pulling latest...")
        subprocess.run(["git", "-C", oc_dir, "pull"], check=True)
    else:
        print(f"OpenClaw dir exists but is not a git repo — skipping git update.")

    if not os.path.isdir(venv_dir):
        print(f"Creating virtual environment at {venv_dir}")
        venv.create(venv_dir, with_pip=True)

    if os.name == "nt":
        python_path = os.path.join(venv_dir, "Scripts", "python")
        pip_path = os.path.join(venv_dir, "Scripts", "pip")
    else:
        python_path = os.path.join(venv_dir, "bin", "python")
        pip_path = os.path.join(venv_dir, "bin", "pip")

    print("Upgrading pip...")
    subprocess.run([python_path, "-m", "pip", "install", "--upgrade", "pip"], check=True)

    print("Installing OpenClaw dependencies...")
    result = subprocess.run(
        [pip_path, "install", "-e", ".[all]"],
        cwd=oc_dir,
        capture_output=True,
    )
    if result.returncode != 0:
        print("Retrying with base install (no extras)...")
        subprocess.run([pip_path, "install", "-e", "."], cwd=oc_dir, check=True)

    print("OpenClaw installation complete.")
    return {
        "installed": True,
        "install_path": oc_dir,
        "venv_path": venv_dir,
        "skipped": False,
    }


def hook_verify(context: Dict[str, Any]) -> bool:
    user_home = context.get("USER_HOME", os.path.expanduser("~"))

    # Check for the node binary first (primary path)
    binary_path = os.path.join(user_home, ".hermes", "node", "bin", "openclaw")
    if os.path.isfile(binary_path) and os.access(binary_path, os.X_OK):
        print(f"OpenClaw binary verified: {binary_path}")
        return True

    # Fallback: check for the old git-repo venv path
    venv_dir = os.path.join(user_home, ".openclaw", "hermes-openclaw", "venv")
    if os.name == "nt":
        python_path = os.path.join(venv_dir, "Scripts", "python.exe")
    else:
        python_path = os.path.join(venv_dir, "bin", "python")

    if os.path.isfile(python_path) and os.access(python_path, os.X_OK):
        print(f"OpenClaw venv verified: {python_path}")
        return True

    raise RuntimeError(f"OpenClaw not found — checked binary at {binary_path} and venv at {venv_dir}")


def hook_cleanup(context: Dict[str, Any]) -> None:
    pass