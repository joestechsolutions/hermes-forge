"""
GitNexus Plugin

Installs GitNexus CLI via npm.
"""

import subprocess
from typing import Any, Dict


def command_exists(cmd: str) -> bool:
    """Check if a command exists in PATH."""
    try:
        subprocess.run(["which", cmd], capture_output=True, check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def get_gitnexus_version() -> str:
    """Get GitNexus version string."""
    result = subprocess.run(["gitnexus", "--version"], capture_output=True, text=True, check=True)
    return result.stdout.strip()


def hook_check_prerequisites(context: Dict[str, Any]) -> bool:
    """
    Check if GitNexus is already installed.

    Returns True if gitnexus command exists, False otherwise.
    """
    if command_exists("gitnexus"):
        print("GitNexus is already installed.")
        return True
    print("GitNexus is not installed.")
    return False


def hook_install(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Install GitNexus globally via npm.

    Returns:
        Dict with installation results, including version.
    """
    print("Installing GitNexus...")

    subprocess.run(["npm", "install", "-g", "gitnexus"], check=True)

    version = get_gitnexus_version()
    print(f"GitNexus installed: {version}")

    return {
        "installed": True,
        "version": version
    }


def hook_verify(context: Dict[str, Any]) -> bool:
    """
    Verify GitNexus installation.

    Returns True if gitnexus --version succeeds, raises otherwise.
    """
    try:
        version = get_gitnexus_version()
        print(f"GitNexus verification passed: {version}")
        return True
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"GitNexus verification failed: {e}")


def hook_cleanup(context: Dict[str, Any]) -> None:
    """
    Clean up npm cache.
    """
    print("Cleaning up npm cache...")
    subprocess.run(["npm", "cache", "clean", "--force"], check=True)
