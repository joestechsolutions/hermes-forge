"""
Hermes Agent Plugin

Clones and installs the Hermes Agent with all dependencies.
"""

import os
import subprocess
import venv
from typing import Any, Dict


def command_exists(cmd: str) -> bool:
    """Check if a command exists in PATH."""
    try:
        subprocess.run(["which", cmd], capture_output=True, check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def hook_check_prerequisites(context: Dict[str, Any]) -> bool:
    """
    Check if Hermes Agent is already installed.

    Checks if ~/.hermes/hermes-agent directory exists.

    Returns True if installed, False otherwise.
    """
    user_home = context.get("USER_HOME", os.path.expanduser("~"))
    hermes_agent_dir = os.path.join(user_home, ".hermes", "hermes-agent")

    if os.path.isdir(hermes_agent_dir):
        print(f"Hermes Agent already exists at {hermes_agent_dir}")
        return True

    print(f"Hermes Agent not found at {hermes_agent_dir}")
    return False


def hook_install(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Clone Hermes Agent repository, create virtual environment, and install with all extras.

    Returns:
        Dict with installation results, including install path.
    """
    print("Installing Hermes Agent...")

    user_home = context.get("USER_HOME", os.path.expanduser("~"))
    hermes_home = os.path.join(user_home, ".hermes")
    hermes_agent_dir = os.path.join(hermes_home, "hermes-agent")
    venv_dir = os.path.join(hermes_agent_dir, "venv")

    # Ensure parent directory exists
    os.makedirs(hermes_home, exist_ok=True)

    # Repository URL (can be overridden via context)
    repo_url = context.get("HERMES_AGENT_REPO", "https://github.com/nousresearch/hermes-agent.git")

    # Clone repository if not exists
    if not os.path.isdir(hermes_agent_dir):
        print(f"Cloning {repo_url} into {hermes_agent_dir}")
        subprocess.run(["git", "clone", repo_url, hermes_agent_dir], check=True)
    else:
        print(f"Directory {hermes_agent_dir} already exists, pulling latest...")
        subprocess.run(["git", "-C", hermes_agent_dir, "pull"], check=True)

    # Create virtual environment
    print(f"Creating virtual environment at {venv_dir}")
    venv.create(venv_dir, with_pip=True)

    # Get path to python and pip in venv
    if os.name == "nt":
        python_path = os.path.join(venv_dir, "Scripts", "python")
        pip_path = os.path.join(venv_dir, "Scripts", "pip")
    else:
        python_path = os.path.join(venv_dir, "bin", "python")
        pip_path = os.path.join(venv_dir, "bin", "pip")

    # Upgrade pip
    subprocess.run([python_path, "-m", "pip", "install", "--upgrade", "pip"], check=True)

    # Install Hermes Agent with all extras
    print("Installing Hermes Agent with [all] extras...")
    subprocess.run([pip_path, "install", "-e", ".[all]"], cwd=hermes_agent_dir, check=True)

    print("Hermes Agent installation complete.")
    return {
        "installed": True,
        "install_path": hermes_agent_dir,
        "venv_path": venv_dir
    }


def hook_verify(context: Dict[str, Any]) -> bool:
    """
    Verify Hermes Agent installation by checking if the venv python binary exists.

    Returns True if venv binary exists, raises RuntimeError otherwise.
    """
    user_home = context.get("USER_HOME", os.path.expanduser("~"))
    venv_dir = os.path.join(user_home, ".hermes", "hermes-agent", "venv")

    if os.name == "nt":
        python_path = os.path.join(venv_dir, "Scripts", "python.exe")
    else:
        python_path = os.path.join(venv_dir, "bin", "python")

    if os.path.isfile(python_path) and os.access(python_path, os.X_OK):
        print(f"Hermes Agent venv verified: {python_path}")
        return True
    else:
        raise RuntimeError(f"Hermes Agent venv not found or not executable: {python_path}")


def hook_cleanup(context: Dict[str, Any]) -> None:
    """
    No cleanup needed for Hermes Agent.
    """
    pass
