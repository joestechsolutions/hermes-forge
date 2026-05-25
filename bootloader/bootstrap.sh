#!/usr/bin/env bash
#
# bootstrap.sh — Bootstrap the Hermes Infrastructure Suite Bootloader
#
# Supports Linux (Ubuntu/Debian) and macOS.
# Linux: runs as root, uses apt + systemd + iptables.
# macOS: runs as user, uses brew + launchd + pfctl.
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OS="$(uname -s)"

# ─── Usage ───────────────────────────────────────────────────────────────────
if [[ "${1:-}" == "--help" ]] || [[ "${1:-}" == "-h" ]]; then
    echo "Hermes Forge Bootloader"
    echo ""
    echo "Usage: bash bootstrap.sh [--help] [run|list] [options]"
    echo ""
    echo "Commands:"
    echo "  run        Run the bootloader (default)"
    echo "  list       List available plugins"
    echo ""
    echo "Options:"
    echo "  --phase PHASE   Run a specific phase (prereq|install|verify|cleanup|all)"
    echo "  --force         Re-run completed phases"
    echo "  --dry-run       Print actions without executing"
    echo "  --snapshot NAME Take a snapshot before install"
    echo "  --restore NAME  Restore from snapshot before running"
    echo ""
    echo "Supported OS: Linux (Ubuntu/Debian), macOS"
    exit 0
fi

# ─── OS Detection ────────────────────────────────────────────────────────────
echo "[bootstrap] Detected OS: ${OS}"

case "$OS" in
    Linux)
        echo "[bootstrap] Linux detected — using apt + systemd + iptables"

        # Check for root/sudo
        if [ "$(id -u)" -ne 0 ]; then
            echo "[ERROR] Linux requires root/sudo."
            echo "  Run: sudo bash bootstrap.sh $*"
            exit 1
        fi

        # Ensure essential system tools
        echo "[bootstrap] Ensuring system dependencies (Linux)..."
        apt-get update -qq 2>/dev/null || true
        apt-get install -y -qq python3 python3-venv python3-pip git curl 2>/dev/null || true

        # Install bootloader
        cd "$SCRIPT_DIR"
        echo "[bootstrap] Installing bootloader..."
        pip install -e . --quiet --break-system-packages 2>/dev/null || \
            pip install -e . --break-system-packages

        echo "[bootstrap] Running bootloader CLI..."
        python3 -m bootloader.cli "$@"
        ;;

    Darwin)
        echo "[bootstrap] macOS detected — using brew + launchd + pfctl"

        # Check for Xcode Command Line Tools
        if ! xcode-select -p &>/dev/null; then
            echo "[bootstrap] Installing Xcode Command Line Tools..."
            xcode-select --install
            echo "[WARN] Xcode CLT install started. Re-run bootstrap after it completes."
            exit 1
        fi

        # Ensure Homebrew
        if ! command -v brew &>/dev/null; then
            echo "[bootstrap] Installing Homebrew..."
            /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
            # Add brew to PATH (Apple Silicon path)
            if [ -f /opt/homebrew/bin/brew ]; then
                eval "$(/opt/homebrew/bin/brew shellenv)"
            fi
        fi

        # Ensure Python 3
        if ! command -v python3 &>/dev/null; then
            echo "[bootstrap] Installing Python 3..."
            brew install python@3.12
        fi

        # Install bootloader
        cd "$SCRIPT_DIR"
        echo "[bootstrap] Installing bootloader..."
        pip3 install -e . --quiet --user 2>/dev/null || \
            pip3 install -e . --user

        echo "[bootstrap] Running bootloader CLI..."
        python3 -m bootloader.cli "$@"
        ;;

    *)
        echo "[ERROR] Unsupported OS: ${OS}"
        echo "  Supported: Linux (Ubuntu/Debian), macOS"
        exit 1
        ;;
esac