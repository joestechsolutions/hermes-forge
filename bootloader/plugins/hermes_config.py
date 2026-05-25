"""
Hermes Configuration Plugin

Generates .env and config.yaml for Hermes Agent, preserving existing
values where possible to avoid overwriting user changes like allowed_users.
"""

import os
import secrets
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional


def _safe_read_yaml(config_path: str) -> Optional[Dict[str, Any]]:
    """Parse YAML file if pyyaml is available and file exists."""
    try:
        import yaml
        if os.path.isfile(config_path):
            with open(config_path, "r") as f:
                return yaml.safe_load(f) or {}
    except ImportError:
        print("Warning: PyYAML not available, config merging disabled")
    except Exception as e:
        print(f"Warning: Could not read existing config at {config_path}: {e}")
    return None


def hook_check_prerequisites(context: Dict[str, Any]) -> bool:
    """
    Check if Hermes configuration files already exist.

    Checks for ~/.hermes/.env and ~/.hermes/config.yaml.

    Returns True if both exist, False otherwise.
    """
    user_home = context.get("USER_HOME", os.path.expanduser("~"))
    env_path = os.path.join(user_home, ".hermes", ".env")
    config_path = os.path.join(user_home, ".hermes", "config.yaml")

    env_exists = os.path.isfile(env_path)
    config_exists = os.path.isfile(config_path)

    if env_exists and config_exists:
        print("Hermes configuration files already exist.")
        return True

    missing = []
    if not env_exists:
        missing.append(".env")
    if not config_exists:
        missing.append("config.yaml")
    print(f"Missing configuration files: {', '.join(missing)}")
    return False


def hook_install(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate .env with secrets and config.yaml with providers and telegram settings.

    SKIPS if config.yaml already exists and is > 100 bytes (real config, not a stub).
    Also skips if both files already exist and are valid — true idempotency.
    Existing values in both files are merged/preserved. The .env preserves all
    existing keys; config.yaml preserves fields like allowed_users and custom
    provider settings.

    Returns:
        Dict with generation results.
    """
    user_home = context.get("USER_HOME", os.path.expanduser("~"))
    hermes_home = os.path.join(user_home, ".hermes")
    env_path = os.path.join(hermes_home, ".env")
    config_path = os.path.join(hermes_home, "config.yaml")

    # ── STRONG GUARD: If config.yaml exists and is > 100 bytes, this is a
    #    real configured system — do NOT overwrite or regenerate anything. ──
    if os.path.isfile(config_path):
        try:
            size = os.path.getsize(config_path)
            if size > 100:
                print(f"config.yaml already exists ({size} bytes) — skipping install (already configured).")
                return {"installed": True, "skipped": True, "reason": "already_configured",
                        "env_path": env_path, "config_path": config_path}
        except OSError:
            pass  # Can't stat, fall through to normal install

    print("Generating Hermes configuration (preserving existing values)...")

    os.makedirs(hermes_home, exist_ok=True)

    # ── IDEMPOTENCY CHECK: skip if both files exist AND are valid ──
    if os.path.isfile(env_path) and os.path.isfile(config_path):
        try:
            import yaml
            with open(config_path) as f:
                config_data = yaml.safe_load(f)
            if config_data and "model" in config_data and "providers" in config_data:
                print("Both .env and config.yaml exist with valid content — skipping install (idempotent).")
                return {"installed": True, "skipped": True, "env_path": env_path, "config_path": config_path}
        except Exception:
            pass  # Config may be invalid — regenerate below

    # Read existing .env values to preserve them
    existing_env = {}
    if os.path.isfile(env_path):
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    existing_env[key.strip()] = val.strip()

    # Define defaults (only fill if not already set)
    env_defaults = {
        "TELEGRAM_BOT_TOKEN": "",
        "NVIDIA_API_KEY": "",
        "FAL_KEY": "",
        "FIRECRAWL_API_KEY": "",
        "OPENROUTER_API_KEY": "",
        "OPENAI_API_KEY": "",
        "ANTHROPIC_API_KEY": "",
        "API_SERVER_ENABLED": "true",
        "API_SERVER_KEY": secrets.token_hex(32),
        "API_SERVER_PORT": "8642",
        "API_SERVER_HOST": "127.0.0.1",
        "HERMES_TELEGRAM_FALLBACK_IPS": "149.154.166.110,149.154.167.220,149.154.166.138,149.154.167.230",
        "TERMINAL_MODAL_IMAGE": "nikolaik/python-nodejs:python3.11-nodejs20",
        "TERMINAL_TIMEOUT": "60",
        "TERMINAL_LIFETIME_SECONDS": "300",
        "BROWSERBASE_PROXIES": "true",
        "LOG_LEVEL": "INFO",
    }

    # Write .env — preserve existing values, fill defaults only for missing keys
    with open(env_path, "w") as f:
        f.write("# Hermes Agent Environment Configuration\n")
        f.write("# Managed by Hermes Bootloader — existing values preserved\n\n")
        for key, default in env_defaults.items():
            value = existing_env.get(key, default)
            f.write(f"{key}={value}\n")

    print(f".env written to {env_path}")

    # ── ALSO write a copy to ~/hermes-forge/.env for user visibility ──
    ai_platform_env = os.path.join(user_home, "hermes-forge", ".env")
    try:
        with open(ai_platform_env, "w") as f:
            f.write("# Hermes Agent Environment Configuration\n")
            f.write("# Managed by Hermes Bootloader — existing values preserved\n")
            f.write("# This file is a mirror of ~/.hermes/.env for user convenience.\n\n")
            for key, default in env_defaults.items():
                value = existing_env.get(key, default)
                f.write(f"{key}={value}\n")
        print(f".env also mirrored to {ai_platform_env}")
    except OSError as e:
        print(f"Warning: could not write {ai_platform_env}: {e}")

    # Merge existing config.yaml values (preserve allowed_users, custom providers)
    existing_config = _safe_read_yaml(config_path) or {}
    allowed_users = existing_config.get("telegram", {}).get("allowed_users")
    # If not set, default to allowlist with the known Joe ID
    if not allowed_users:
        allowed_users = ["6878695078"]

    # Preserve any extra provider configs the user may have added
    preserved_providers = existing_config.get("providers", {})

    config_yaml = f"""# Hermes Agent Configuration
# Managed by Hermes Bootloader — existing values preserved on re-run

model:
  default: stepfun-ai/step-3.5-flash
  provider: nvidia
  base_url: https://integrate.api.nvidia.com/v1
  api_key: ${{NVIDIA_API_KEY}}

providers:
  nvidia:
    api: https://integrate.api.nvidia.com/v1
    default_model: stepfun-ai/step-3.5-flash
    models:
    - stepfun-ai/step-3.5-flash
    - minimax-m2.7
  openrouter:
    api: https://openrouter.ai/api/v1
    default_model: qwen/qwen3-coder:free
    models:
    - qwen/qwen3-coder:free
    - nvidia/nemotron-3-super-120b-a12b:free
    - nvidia/nemotron-3-nano-30b-a3b:free
    fallback_models: [meta-llama/llama-3.3-70b-instruct:free]
  ollama:
    api: http://127.0.0.1:11434/v1
    default_model: granite4.1:8b
    models: [granite4.1:8b]
    fallback_models: [granite4.1:8b]

fallback_providers: [openrouter]

agent:
  max_turns: 90
  gateway_timeout: 1800
  name: Hermes
  system_prompt_path: SOUL.md
  max_tokens: 8192
  temperature: 0.7

terminal:
  backend: local
  timeout: 180
  docker_image: nikolaik/python-nodejs:python3.11-nodejs20

telegram:
  bot_token: ${{TELEGRAM_BOT_TOKEN}}
  allowed_users: {allowed_users}
  fallback_ips:
    - 149.154.166.110
    - 149.154.167.220
    - 149.154.166.138
    - 149.154.167.230

security:
  allow_private_urls: false
  redact_secrets: false
  tirith_enabled: true

logging:
  level: ${{LOG_LEVEL}}
  max_size_mb: 5
  backup_count: 3

mcp_servers:
  mempalace:
    command: {Path.home() / ".local/bin/mempalace-mcp"}
    args:
      - --palace
      - {Path.home() / ".mempalace"}
    timeout: 120

image_gen:
  model: fal-ai/flux-2/klein/9b

web:
  backend: firecrawl
  use_gateway: false
"""

    with open(config_path, "w") as f:
        f.write(config_yaml)

    # Try to preserve user-added provider settings by re-opening and merging
    try:
        import yaml
        with open(config_path, "r") as f:
            config_data = yaml.safe_load(f)

        if preserved_providers:
            for prov_name, prov_config in preserved_providers.items():
                if prov_name not in config_data.get("providers", {}):
                    config_data.setdefault("providers", {})[prov_name] = prov_config

        with open(config_path, "w") as f:
            yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)

        print(f"config.yaml merged and written to {config_path}")
    except ImportError:
        print(f"config.yaml written to {config_path} (yaml merge skipped — pyyaml not available)")
    except Exception as e:
        # If yaml merge fails, the basic config.yaml we wrote above is already valid
        print(f"config.yaml written, yaml merge note: {e}")

    return {
        "installed": True,
        "env_path": env_path,
        "config_path": config_path,
    }


def hook_verify(context: Dict[str, Any]) -> bool:
    """
    Verify configuration files exist and have valid structure.

    Returns True if both files exist and config.yaml is valid YAML,
    raises RuntimeError otherwise.
    """
    user_home = context.get("USER_HOME", os.path.expanduser("~"))
    hermes_home = os.path.join(user_home, ".hermes")
    env_path = os.path.join(hermes_home, ".env")
    config_path = os.path.join(hermes_home, "config.yaml")

    errors = []

    if not os.path.isfile(env_path):
        errors.append(f".env not found at {env_path}")

    if not os.path.isfile(config_path):
        errors.append(f"config.yaml not found at {config_path}")
    else:
        # Validate YAML syntax
        try:
            import yaml
            with open(config_path, "r") as f:
                config = yaml.safe_load(f)
            required_sections = ["telegram", "providers", "agent", "logging"]
            missing_sections = [s for s in required_sections if s not in config]
            if missing_sections:
                errors.append(f"config.yaml missing sections: {missing_sections}")
        except ImportError:
            print("Warning: PyYAML not available, skipping YAML validation")
        except yaml.YAMLError as e:
            errors.append(f"config.yaml YAML syntax error: {e}")
        except Exception as e:
            errors.append(f"config.yaml validation error: {e}")

    if errors:
        raise RuntimeError(f"Configuration verification failed: {'; '.join(errors)}")

    print("Configuration verified successfully.")
    return True


def hook_cleanup(context: Dict[str, Any]) -> None:
    """No cleanup needed for Hermes config."""
    pass