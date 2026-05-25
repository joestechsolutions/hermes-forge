"""MemPalace Plugin

Checks for existing MemPalace installation at ~/mempalace/,
verifies the .venv (created by uv) and MCP/CLI binaries.
"""

import os
import subprocess
from typing import Any, Dict


MEMPALACE_REPO = "https://github.com/nousresearch/MemPalace.git"
MEMPALACE_DIR_NAME = "mempalace"


def _mempalace_dir(user_home: str) -> str:
    return os.path.join(user_home, MEMPALACE_DIR_NAME)


def _venv_dir(user_home: str) -> str:
    return os.path.join(_mempalace_dir(user_home), ".venv")


def _python_path(user_home: str) -> str:
    return os.path.join(_venv_dir(user_home), "bin", "python3")


def _mcp_bin(user_home: str) -> str:
    return os.path.join(_venv_dir(user_home), "bin", "mempalace-mcp")


def _cli_bin(user_home: str) -> str:
    return os.path.join(_venv_dir(user_home), "bin", "mempalace")


def hook_check_prerequisites(context: Dict[str, Any]) -> bool:
    user_home = context.get("USER_HOME", os.path.expanduser("~"))
    mp_dir = _mempalace_dir(user_home)
    if os.path.isdir(mp_dir):
        print(f"MemPalace already exists at {mp_dir}")
    print("MemPalace can be installed (or is already present).")
    return True


def hook_install(context: Dict[str, Any]) -> Dict[str, Any]:
    print("Installing MemPalace...")

    user_home = context.get("USER_HOME", os.path.expanduser("~"))
    mp_dir = _mempalace_dir(user_home)
    vdir = _venv_dir(user_home)
    python_bin = _python_path(user_home)
    mcp_bin = _mcp_bin(user_home)
    cli_bin = _cli_bin(user_home)

    if not os.path.isdir(mp_dir):
        print(f"Cloning {MEMPALACE_REPO} into {mp_dir}")
        subprocess.run(["git", "clone", MEMPALACE_REPO, mp_dir], check=True)
    else:
        print(f"MemPalace dir exists, pulling latest...")
        subprocess.run(["git", "-C", mp_dir, "pull"], check=True)

    if not os.path.isdir(vdir):
        print(f"Creating virtual environment at {vdir} with uv...")
        subprocess.run(
            ["uv", "venv", vdir, "--python=3.14"],
            cwd=mp_dir,
            check=True,
        )

    print("Installing MemPalace with uv...")
    subprocess.run(
        ["uv", "pip", "install", "-e", ".[all]"],
        cwd=mp_dir,
        check=True,
    )

    return {
        "installed": True,
        "install_path": mp_dir,
        "venv_path": vdir,
        "python_path": python_bin,
        "mcp_bin": mcp_bin,
        "cli_bin": cli_bin,
        "skipped": False,
    }


def hook_verify(context: Dict[str, Any]) -> bool:
    user_home = context.get("USER_HOME", os.path.expanduser("~"))
    vdir = _venv_dir(user_home)
    python_bin = _python_path(user_home)
    mcp_bin = _mcp_bin(user_home)
    cli_bin = _cli_bin(user_home)
    mp_dir = _mempalace_dir(user_home)

    if not os.path.isdir(mp_dir):
        raise RuntimeError(f"MemPalace directory not found: {mp_dir}")
    if not os.path.isdir(vdir):
        raise RuntimeError(f"MemPalace .venv not found: {vdir}")
    if not os.path.isfile(python_bin):
        raise RuntimeError(f"MemPalace venv python not found: {python_bin}")
    if os.name != "nt" and not os.access(python_bin, os.X_OK):
        raise RuntimeError(f"MemPalace venv python not executable: {python_bin}")
    if not os.path.isfile(mcp_bin):
        raise RuntimeError(f"MemPalace MCP binary not found: {mcp_bin}")
    if not os.path.isfile(cli_bin):
        raise RuntimeError(f"MemPalace CLI binary not found: {cli_bin}")
    print(f"MemPalace verified: python={python_bin}, mcp={mcp_bin}, cli={cli_bin}")
    return True


def hook_cleanup(context: Dict[str, Any]) -> None:
    pass