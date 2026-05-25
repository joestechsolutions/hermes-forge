"""
Pnpm Plugin

Installs pnpm via corepack.
"""

import subprocess
from typing import Any, Dict


def _command_exists(cmd: str) -> bool:
    try:
        subprocess.run(["which", cmd], capture_output=True, check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def hook_check_prerequisites(context: Dict[str, Any]) -> bool:
    if _command_exists("pnpm"):
        print("pnpm is already installed.")
        return True
    print("pnpm not found.")
    return False


def hook_install(context: Dict[str, Any]) -> Dict[str, Any]:
    if _command_exists("pnpm"):
        print("pnpm already installed — skipping.")
        return {"installed": True, "skipped": True}

    print("Enabling corepack...")
    subprocess.run(["corepack", "enable"], check=True)

    print("Preparing pnpm via corepack...")
    subprocess.run(["corepack", "prepare", "pnpm@latest", "--activate"], check=True)

    return {"installed": True, "skipped": False}


def hook_verify(context: Dict[str, Any]) -> bool:
    result = subprocess.run(["pnpm", "--version"], capture_output=True, check=True)
    print(f"pnpm version: {result.stdout.decode().strip()}")
    return True


def hook_cleanup(context: Dict[str, Any]) -> None:
    pass