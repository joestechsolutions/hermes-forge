"""
Docker Plugin

Installs Docker using the official get.docker.com script.
"""

import platform
import subprocess
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
    Check if Docker is already installed.

    Returns True if docker command exists, False otherwise.
    """
    if command_exists("docker"):
        print("Docker is already installed.")
        return True
    print("Docker is not installed.")
    return False


def hook_install(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Install Docker using the official install script.

    Returns:
        Dict with installation results.
    """
    print("Installing Docker...")

    # Run official Docker installation script
    subprocess.run(
        ["curl", "-fsSL", "https://get.docker.com", "-o", "/tmp/get_docker.sh"],
        check=True
    )
    subprocess.run(["bash", "/tmp/get_docker.sh"], check=True)

    # Get USER_HOME from context or default
    user_home = context.get("USER_HOME", "/root")

    # Add current user to docker group (Linux only — Docker Desktop on macOS doesn't use a docker group)
    if platform.system() != "Darwin":
        try:
            import os
            if os.geteuid() != 0:
                subprocess.run(["usermod", "-aG", "docker", context.get("USER", "lurkr")], check=True)
                print(f"Added user {context.get('USER', 'lurkr')} to docker group.")
        except Exception as e:
            print(f"Note: Could not add user to docker group: {e}")
    else:
        print("macOS detected: skipping usermod (Docker Desktop manages group/daemon access).")

    return {
        "installed": True
    }


def hook_verify(context: Dict[str, Any]) -> bool:
    """
    Verify Docker installation.

    Returns True if docker --version succeeds, raises otherwise.
    """
    try:
        result = subprocess.run(["docker", "--version"], capture_output=True, text=True, check=True)
        print(f"Docker verification passed: {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Docker verification failed: {e}")


def hook_cleanup(context: Dict[str, Any]) -> None:
    """
    No cleanup needed for Docker.
    """
    pass
