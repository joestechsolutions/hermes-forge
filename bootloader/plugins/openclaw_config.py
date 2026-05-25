"""
OpenClaw Configuration Plugin

Generates ~/.openclaw/config.yaml for OpenClaw, preserving existing
values (especially allowed_users) on re-run.
"""

import os
from typing import Any, Dict, Optional


def _safe_read_yaml(path: str) -> Optional[Dict[str, Any]]:
    """Parse YAML file if pyyaml is available and file exists."""
    if not os.path.isfile(path):
        return None
    try:
        import yaml
        with open(path, "r") as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        print("Warning: PyYAML not available, config merging disabled")
    except Exception as e:
        print(f"Warning: Could not read existing config at {path}: {e}")
    return None


def hook_check_prerequisites(context: Dict[str, Any]) -> bool:
    """
    Check if OpenClaw config can be generated/installed.

    Always returns True — install handles idempotency and preserves
    existing values (allowed_users) on re-run.
    """
    user_home = context.get("USER_HOME", os.path.expanduser("~"))
    config_path = os.path.join(user_home, ".openclaw", "config.yaml")
    if os.path.isfile(config_path):
        print("OpenClaw config already exists — will preserve on re-run.")
    else:
        print("OpenClaw config will be generated.")
    return True


def hook_install(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate ~/.openclaw/config.yaml for OpenClaw.

    Preserves existing allowed_users and any custom provider settings
    to avoid overwriting user changes on re-run.

    Returns:
        Dict with generation results.
    """
    print("Generating OpenClaw configuration (preserving allowed_users)...")

    user_home = context.get("USER_HOME", os.path.expanduser("~"))
    openclaw_dir = os.path.join(user_home, ".openclaw")
    config_path = os.path.join(openclaw_dir, "config.yaml")
    os.makedirs(openclaw_dir, exist_ok=True)

    # Preserve existing values — THE MOST IMPORTANT PART
    existing = _safe_read_yaml(config_path) or {}
    allowed_users = existing.get("telegram", {}).get("allowed_users")
    if not allowed_users:
        allowed_users = ["6878695078"]

    # Preserve any custom provider configs the user may have added
    preserved_providers = existing.get("providers", {})

    config_data = {
        "telegram": {
            "bot_token": "${TELEGRAM_BOT_TOKEN}",
            "allowed_users": allowed_users,
            "fallback_ips": [
                "149.154.166.110",
                "149.154.167.220",
                "149.154.166.138",
                "149.154.167.230",
            ],
        },
        "server": {
            "port": 18789,
            "host": "127.0.0.1",
            "log_level": "info",
        },
        "providers": preserved_providers,
    }

    # Write YAML using pyyaml if available
    try:
        import yaml
        with open(config_path, "w") as f:
            yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)
        print(f"config.yaml written to {config_path}")
    except ImportError:
        print(f"config.yaml write skipped — pyyaml not available at {config_path}")
    except Exception as e:
        raise RuntimeError(f"Failed to write config.yaml: {e}")

    return {"installed": True, "config_path": config_path}


def hook_verify(context: Dict[str, Any]) -> bool:
    """
    Verify configuration file exists and has valid structure.

    Returns True if file exists and config.yaml has required keys,
    raises RuntimeError otherwise.
    """
    user_home = context.get("USER_HOME", os.path.expanduser("~"))
    config_path = os.path.join(user_home, ".openclaw", "config.yaml")

    if not os.path.isfile(config_path):
        raise RuntimeError(f"OpenClaw config not found at {config_path}")

    # Validate YAML structure
    try:
        import yaml
        with open(config_path, "r") as f:
            cfg = yaml.safe_load(f)
        # Note: telegram key is optional — Hermes handles Telegram,
        # OpenClaw Telegram is intentionally disabled.
        required = ["server"]
        missing = [k for k in required if k not in cfg]
        if missing:
            raise RuntimeError(f"OpenClaw config missing keys: {missing}")
    except ImportError:
        print("Warning: PyYAML not available, skipping YAML validation")
    except yaml.YAMLError as e:
        raise RuntimeError(f"OpenClaw config YAML syntax error: {e}")

    print("OpenClaw config verified.")
    return True


def hook_cleanup(context: Dict[str, Any]) -> None:
    """No cleanup needed for OpenClaw config."""
    pass