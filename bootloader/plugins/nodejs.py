"""
Node.js Plugin

Installs Node.js 22.x using:
  - Linux: NodeSource apt repository
  - macOS: Homebrew (brew install node@22)
"""

import subprocess
from typing import Any, Dict

from bootloader.lib.platform import IS_MACOS


def command_exists(cmd: str) -> bool:
    """Check if a command exists in PATH."""
    try:
        subprocess.run(["which", cmd], capture_output=True, check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def get_node_version() -> str:
    """Get installed Node.js version string."""
    result = subprocess.run(["node", "--version"], capture_output=True, text=True, check=True)
    return result.stdout.strip()


def hook_check_prerequisites(context: Dict[str, Any]) -> bool:
    """
    Check if Node.js is installed and version >= 22.

    Returns True if Node.js 22+ is present, False otherwise.
    """
    if not command_exists("node"):
        print("Node.js is not installed.")
        return False

    version = get_node_version()
    major_version = int(version.lstrip('v').split('.')[0])

    if major_version >= 22:
        print(f"Node.js {version} is installed (required: 22.x).")
        return True
    else:
        print(f"Node.js {version} is installed but version >= 22 required.")
        return False


def hook_install(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Install Node.js 22.x.

    Linux: Uses NodeSource apt repository.
    macOS: Uses Homebrew (brew install node@22).

    Returns:
        Dict with installation results.
    """
    print("Installing Node.js 22.x...")

    if IS_MACOS:
        # Ensure Homebrew is available
        subprocess.run(
            ["which", "brew"], capture_output=True, check=True,
        )
        subprocess.run(["brew", "install", "node@22"], check=True)
        # Homebrew's node@22 is keg-only — link it
        subprocess.run(["brew", "link", "--overwrite", "node@22"], check=True)
    else:
        # Linux: Download and run NodeSource setup script
        subprocess.run(
            ["curl", "-fsSL", "https://deb.nodesource.com/setup_22.x", "-o", "/tmp/nodesource_setup.sh"],
            check=True,
        )
        subprocess.run(["bash", "/tmp/nodesource_setup.sh"], check=True)
        subprocess.run(["apt-get", "install", "-y", "nodejs"], check=True)

    # Verify installation
    version = get_node_version()
    print(f"Node.js installed: {version}")

    return {
        "installed": True,
        "version": version
    }


def hook_verify(context: Dict[str, Any]) -> bool:
    """
    Verify Node.js installation.

    Returns True if node --version succeeds, raises otherwise.
    """
    try:
        version = get_node_version()
        major_version = int(version.lstrip('v').split('.')[0])
        if major_version < 22:
            raise RuntimeError(f"Node.js version {version} is less than required 22.x")
        print(f"Node.js verification passed: {version}")
        return True
    except Exception as e:
        raise RuntimeError(f"Node.js verification failed: {e}")


def hook_cleanup(context: Dict[str, Any]) -> None:
    """
    No cleanup needed for Node.js.
    """
    pass
