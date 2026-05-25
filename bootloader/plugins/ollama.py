"""
Ollama Plugin

Installs and configures the Ollama service.
- Linux: install via official script, systemd drop-in, systemctl management
- macOS: install via Homebrew, ~/.zshrc env config, brew services management
"""

import os
import subprocess
from typing import Any, Dict

from bootloader.lib.platform import IS_MACOS, pkg_install, pkg_update, pkg_ensure_brew


def command_exists(cmd: str) -> bool:
    """Check if a command exists in PATH."""
    try:
        subprocess.run(["which", cmd], capture_output=True, check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def _configure_macos_ollama_host() -> None:
    """
    Configure OLLAMA_HOST=127.0.0.1:11434 in ~/.zshrc.
    On macOS, brew services do not read systemd-style Environment= directives,
    so we set the env var in the user's shell profile.
    """
    zshrc = os.path.expanduser("~/.zshrc")
    env_line = 'export OLLAMA_HOST="127.0.0.1:11434"'

    # Read existing content if file exists
    existing = ""
    if os.path.isfile(zshrc):
        with open(zshrc) as f:
            existing = f.read()

    # Check if already configured — avoid duplicate entries
    if "OLLAMA_HOST" in existing:
        print("OLLAMA_HOST already configured in ~/.zshrc.")
        return

    with open(zshrc, "a") as f:
        f.write(f"\n# Ollama — bind to localhost only\n{env_line}\n")
    print(f"Added '{env_line}' to ~/.zshrc")


def hook_check_prerequisites(context: Dict[str, Any]) -> bool:
    """
    Check if Ollama is already installed.

    Returns True if ollama command exists, False otherwise.
    """
    if command_exists("ollama"):
        print("Ollama is already installed.")
        return True
    print("Ollama is not installed.")
    return False


def hook_install(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Install Ollama, configure it to bind to 127.0.0.1, and enable/start the service.

    Returns:
        Dict with installation results.
    """
    print("Installing Ollama...")

    if IS_MACOS:
        # --- macOS path ---
        # Ensure Homebrew is available
        if not pkg_ensure_brew():
            raise RuntimeError("Failed to ensure Homebrew is installed")
        pkg_update()

        # Install ollama via Homebrew
        if not pkg_install(["ollama"]):
            raise RuntimeError("Failed to install ollama via Homebrew")

        # Configure OLLAMA_HOST in ~/.zshrc
        _configure_macos_ollama_host()

        # Start the service via brew services
        print("Starting ollama service via brew services...")
        subprocess.run(
            ["brew", "services", "start", "ollama"],
            check=True,
        )

    else:
        # --- Linux path ---
        # Install Ollama using official script
        subprocess.run(
            ["curl", "-fsSL", "https://ollama.ai/install.sh", "-o", "/tmp/install_ollama.sh"],
            check=True,
        )
        subprocess.run(["bash", "/tmp/install_ollama.sh"], check=True)

        # Configure Ollama to bind only to localhost
        # Create or update /etc/systemd/system/ollama.service drop-in
        print("Configuring Ollama to bind to 127.0.0.1...")
        service_dir = "/etc/systemd/system/ollama.service.d"
        subprocess.run(["mkdir", "-p", service_dir], check=True)

        dropin_content = """[Service]
Environment="OLLAMA_HOST=127.0.0.1:11434"
"""
        subprocess.run(
            ["sh", "-c", f"echo '{dropin_content}' > {service_dir}/bind.conf"],
            check=True,
        )

        # Reload systemd, enable and start service
        subprocess.run(["systemctl", "daemon-reload"], check=True)
        subprocess.run(["systemctl", "enable", "ollama"], check=True)
        subprocess.run(["systemctl", "start", "ollama"], check=True)

    return {"installed": True}


def hook_verify(context: Dict[str, Any]) -> bool:
    """
    Verify Ollama service is active.

    Returns True if ollama is running, raises otherwise.
    """
    if IS_MACOS:
        # Check via brew services list (parses status from output)
        try:
            result = subprocess.run(
                ["brew", "services", "list"],
                capture_output=True,
                text=True,
                check=True,
            )
            # brew services list outputs lines like: ollama  started  lurkr  ~/Library/LaunchAgents/homebrew.mxcl.ollama.plist
            for line in result.stdout.splitlines():
                if line.startswith("ollama"):
                    if "started" in line:
                        print("Ollama service is active (brew services).")
                        return True
                    raise RuntimeError(f"Ollama service status: {line.strip()}")
            raise RuntimeError("Ollama not found in brew services list")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Ollama verification failed: {e}")

    else:
        # Linux: check via systemctl
        try:
            result = subprocess.run(
                ["systemctl", "is-active", "ollama"],
                capture_output=True,
                text=True,
                check=True,
            )
            status = result.stdout.strip()
            if status == "active":
                print("Ollama service is active.")
                return True
            else:
                raise RuntimeError(f"Ollama service status is: {status}")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Ollama verification failed: {e}")


def hook_cleanup(context: Dict[str, Any]) -> None:
    """
    No cleanup needed for Ollama.
    """
    pass