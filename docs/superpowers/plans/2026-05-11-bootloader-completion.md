# Bootloader Completion — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver 8 missing Python plugin files, bootstrap.sh, and tests for the Hermes Bootloader on joBlade (WSL2 Ubuntu). CLI-only verification (no running services required for hook_verify).

**Architecture:** 8 standalone plugin files in `bootloader/plugins/` following the existing module-level hook pattern (`hook_check_prerequisites`, `hook_install`, `hook_verify`, `hook_cleanup`). Idempotent, state-aware, no external deps beyond Python stdlib + subprocess.

**Tech Stack:** Python 3.10+, subprocess, os, pathlib, venv, pyyaml (for config plugins), systemd (via systemctl --user).

---

## Reference Files

Read these before starting any plugin:
- `bootloader/plugins/system_deps.py` — canonical pattern (command_exists helper, _missing helper, 4 hooks)
- `bootloader/plugins/directories.py` — pattern for path-based prereq checks
- `bootloader/plugins/hermes_config.py` — pattern for YAML config reading/merging/preserving allowed_users
- `bootloader/cli.py` — how PluginManager calls hooks

---

## Task 1: `pnpm.py`

**Files:**
- Create: `bootloader/plugins/pnpm.py`

- [ ] **Step 1: Write the failing test**

```python
# bootloader/tests/test_pnpm.py
import unittest
from unittest.mock import patch

class TestPnpm(unittest.TestCase):
    @patch("subprocess.run")
    def test_prereq_pass_when_pnpm_exists(self, mock_run):
        mock_run.return_value = unittest.mock.MagicMock(returncode=0)
        import bootloader.plugins.pnpm as pnpm
        result = pnpm.hook_check_prerequisites({})
        self.assertTrue(result)

    @patch("subprocess.run")
    def test_prereq_fail_when_pnpm_missing(self, mock_run):
        mock_run.side_effect = subprocess.CalledProcessError(1, "which")
        import bootloader.plugins.pnpm as pnpm
        result = pnpm.hook_check_prerequisites({})
        self.assertFalse(result)

    @patch("subprocess.run")
    def test_install_idempotent(self, mock_run):
        # Simulate pnpm already installed
        mock_run.return_value = unittest.mock.MagicMock(returncode=0)
        import bootloader.plugins.pnpm as pnpm
        r1 = pnpm.hook_install({})
        r2 = pnpm.hook_install({})
        # second run should skip
        self.assertTrue(r1.get("installed"))
        self.assertTrue(r2.get("skipped", False))

    @patch("subprocess.run")
    def test_verify_passes(self, mock_run):
        mock_run.return_value = unittest.mock.MagicMock(returncode=0)
        import bootloader.plugins.pnpm as pnpm
        self.assertTrue(pnpm.hook_verify({}))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/lurkr/ai-platform && python3 -m pytest bootloader/tests/test_pnpm.py -v`
Expected: FAIL — `bootloader.plugins.pnpm` has no attribute `hook_check_prerequisites`

- [ ] **Step 3: Write minimal implementation**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/lurkr/ai-platform && python3 -m pytest bootloader/tests/test_pnpm.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add bootloader/plugins/pnpm.py bootloader/tests/test_pnpm.py
git commit -m "feat(bootloader): add pnpm plugin via corepack

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: `openclaw.py`

**Files:**
- Create: `bootloader/plugins/openclaw.py`

- [ ] **Step 1: Write the failing test**

```python
# bootloader/tests/test_openclaw.py
import unittest
import os
import tempfile
from unittest.mock import patch, MagicMock

class TestOpenClaw(unittest.TestCase):
    def setUp(self):
        self.user_home = tempfile.mkdtemp()
        self.context = {"USER_HOME": self.user_home}

    @patch("subprocess.run")
    @patch("os.path.isdir")
    @patch("os.makedirs")
    def test_prereq_returns_false_when_missing(self, mock_makedirs, mock_isdir, mock_run):
        mock_isdir.return_value = False
        import bootloader.plugins.openclaw as oc
        # force reload
        import importlib; importlib.reload(oc)
        result = oc.hook_check_prerequisites(self.context)
        self.assertFalse(result)

    @patch("subprocess.run")
    @patch("os.path.isdir")
    @patch("os.makedirs")
    @patch("bootloader.plugins.openclaw.venv")
    def test_install_creates_venv(self, mock_venv, mock_isdir, mock_makedirs, mock_run):
        mock_isdir.return_value = False
        mock_run.return_value = MagicMock(returncode=0)
        mock_subproc = MagicMock()
        mock_subproc.return_value = MagicMock(returncode=0)
        mock_run.side_effect = [mock_subproc, mock_subproc, mock_subproc, mock_subproc]

        import bootloader.plugins.openclaw as oc
        import importlib; importlib.reload(oc)
        oc.venv.create = MagicMock()

        result = oc.hook_install(self.context)
        self.assertTrue(result["installed"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/lurkr/ai-platform && python3 -m pytest bootloader/tests/test_openclaw.py -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 3: Write minimal implementation**

```python
"""
OpenClaw Plugin

Clones hermes-openclaw repository and installs dependencies.
"""

import os
import subprocess
import venv
from typing import Any, Dict


OPENCLAW_REPO = "https://github.com/nousresearch/hermes-openclaw.git"


def hook_check_prerequisites(context: Dict[str, Any]) -> bool:
    user_home = context.get("USER_HOME", os.path.expanduser("~"))
    oc_dir = os.path.join(user_home, ".openclaw", "hermes-openclaw")
    if os.path.isdir(oc_dir):
        print(f"OpenClaw already exists at {oc_dir}")
        return True
    print(f"OpenClaw not found at {oc_dir}")
    return False


def hook_install(context: Dict[str, Any]) -> Dict[str, Any]:
    print("Installing OpenClaw...")

    user_home = context.get("USER_HOME", os.path.expanduser("~"))
    openclaw_home = os.path.join(user_home, ".openclaw")
    oc_dir = os.path.join(openclaw_home, "hermes-openclaw")
    venv_dir = os.path.join(oc_dir, "venv")

    os.makedirs(openclaw_home, exist_ok=True)

    if not os.path.isdir(oc_dir):
        print(f"Cloning {OPENCLAW_REPO} into {oc_dir}")
        subprocess.run(["git", "clone", OPENCLAW_REPO, oc_dir], check=True)
    else:
        print(f"OpenClaw dir exists, pulling latest...")
        subprocess.run(["git", "-C", oc_dir, "pull"], check=True)

    if not os.path.isdir(venv_dir):
        print(f"Creating virtual environment at {venv_dir}")
        venv.create(venv_dir, with_pip=True)

    python_path = os.path.join(venv_dir, "bin", "python")
    pip_path = os.path.join(venv_dir, "bin", "pip")

    print("Upgrading pip...")
    subprocess.run([python_path, "-m", "pip", "install", "--upgrade", "pip"], check=True)

    print("Installing OpenClaw dependencies...")
    # Try with [all] first, fall back to base install
    result = subprocess.run(
        [pip_path, "install", "-e", ".[all]"],
        cwd=oc_dir,
        capture_output=True,
    )
    if result.returncode != 0:
        print("Retrying with base install (no extras)...")
        subprocess.run([pip_path, "install", "-e", "."], cwd=oc_dir, check=True)

    return {
        "installed": True,
        "install_path": oc_dir,
        "venv_path": venv_dir,
    }


def hook_verify(context: Dict[str, Any]) -> bool:
    user_home = context.get("USER_HOME", os.path.expanduser("~"))
    venv_dir = os.path.join(user_home, ".openclaw", "hermes-openclaw", "venv")
    python_path = os.path.join(venv_dir, "bin", "python")
    if os.path.isfile(python_path) and os.access(python_path, os.X_OK):
        print(f"OpenClaw venv verified: {python_path}")
        return True
    raise RuntimeError(f"OpenClaw venv not found or not executable: {python_path}")


def hook_cleanup(context: Dict[str, Any]) -> None:
    pass
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/lurkr/ai-platform && python3 -m pytest bootloader/tests/test_openclaw.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add bootloader/plugins/openclaw.py bootloader/tests/test_openclaw.py
git commit -m "feat(bootloader): add openclaw plugin

Clones hermes-openclaw, creates venv, installs dependencies.
Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: `openclaw_config.py`

**Files:**
- Create: `bootloader/plugins/openclaw_config.py`

- [ ] **Step 1: Write the failing test**

```python
# bootloader/tests/test_openclaw_config.py
import unittest, tempfile, os, yaml
from unittest.mock import patch

class TestOpenClawConfig(unittest.TestCase):
    def setUp(self):
        self.user_home = tempfile.mkdtemp()
        self.context = {"USER_HOME": self.user_home}
        self.config_path = os.path.join(self.user_home, ".openclaw", "config.yaml")

    def test_prereq_false_when_config_missing(self):
        import bootloader.plugins.openclaw_config as occ; reload = __import__("importlib").modules.get("bootloader.plugins.openclaw_config")
        import importlib; importlib.reload(occ)
        result = occ.hook_check_prerequisites(self.context)
        self.assertFalse(result)

    def test_install_creates_valid_yaml(self):
        import bootloader.plugins.openclaw_config as occ; import importlib; importlib.reload(occ)
        occ.hook_install(self.context)
        self.assertTrue(os.path.isfile(self.config_path))
        with open(self.config_path) as f:
            cfg = yaml.safe_load(f)
        self.assertIn("allowed_users", cfg.get("telegram", {}))

    def test_install_preserves_existing_allowed_users(self):
        # Create existing config with custom allowed_users
        os.makedirs(os.path.join(self.user_home, ".openclaw"), exist_ok=True)
        with open(self.config_path, "w") as f:
            yaml.dump({"telegram": {"allowed_users": ["123456"]}}, f)

        import bootloader.plugins.openclaw_config as occ; import importlib; importlib.reload(occ)
        occ.hook_install(self.context)

        with open(self.config_path) as f:
            cfg = yaml.safe_load(f)
        self.assertIn("123456", cfg["telegram"]["allowed_users"])

    def test_verify_passes_with_valid_yaml(self):
        os.makedirs(os.path.join(self.user_home, ".openclaw"), exist_ok=True)
        with open(self.config_path, "w") as f:
            yaml.dump({"telegram": {"allowed_users": ["6878695078"]}, "server": {"port": 18789}}, f)

        import bootloader.plugins.openclaw_config as occ; import importlib; importlib.reload(occ)
        self.assertTrue(occ.hook_verify(self.context))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/lurkr/ai-platform && python3 -m pytest bootloader/tests/test_openclaw_config.py -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 3: Write minimal implementation**

```python
"""
OpenClaw Configuration Plugin

Generates ~/.openclaw/config.yaml for OpenClaw, preserving existing
values (especially allowed_users) on re-run.
"""

import os
from typing import Any, Dict, Optional

try:
    import yaml
except ImportError:
    yaml = None


def _safe_read_yaml(path: str) -> Optional[Dict[str, Any]]:
    if yaml is None or not os.path.isfile(path):
        return None
    try:
        with open(path, "r") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return None


def hook_check_prerequisites(context: Dict[str, Any]) -> bool:
    user_home = context.get("USER_HOME", os.path.expanduser("~"))
    config_path = os.path.join(user_home, ".openclaw", "config.yaml")
    if os.path.isfile(config_path):
        print("OpenClaw config already exists.")
        return True
    print("OpenClaw config not found.")
    return False


def hook_install(context: Dict[str, Any]) -> Dict[str, Any]:
    print("Generating OpenClaw configuration (preserving allowed_users)...")

    user_home = context.get("USER_HOME", os.path.expanduser("~"))
    openclaw_dir = os.path.join(user_home, ".openclaw")
    config_path = os.path.join(openclaw_dir, "config.yaml")
    os.makedirs(openclaw_dir, exist_ok=True)

    # Preserve existing allowed_users
    existing = _safe_read_yaml(config_path) or {}
    allowed_users = existing.get("telegram", {}).get("allowed_users")
    if not allowed_users:
        allowed_users = ["6878695078"]

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
        "providers": existing.get("providers", {}),
    }

    with open(config_path, "w") as f:
        yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)

    print(f"config.yaml written to {config_path}")
    return {"installed": True, "config_path": config_path}


def hook_verify(context: Dict[str, Any]) -> bool:
    user_home = context.get("USER_HOME", os.path.expanduser("~"))
    config_path = os.path.join(user_home, ".openclaw", "config.yaml")
    if not os.path.isfile(config_path):
        raise RuntimeError("OpenClaw config not found")
    if yaml:
        with open(config_path, "r") as f:
            cfg = yaml.safe_load(f)
        required = ["telegram", "server"]
        missing = [k for k in required if k not in cfg]
        if missing:
            raise RuntimeError(f"OpenClaw config missing keys: {missing}")
    print("OpenClaw config verified.")
    return True


def hook_cleanup(context: Dict[str, Any]) -> None:
    pass
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/lurkr/ai-platform && python3 -m pytest bootloader/tests/test_openclaw_config.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add bootloader/plugins/openclaw_config.py bootloader/tests/test_openclaw_config.py
git commit -m "feat(bootloader): add openclaw_config plugin

Preserves allowed_users on re-run. Follows hermes_config pattern.
Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: `open_design.py`

**Files:**
- Create: `bootloader/plugins/open_design.py`

- [ ] **Step 1: Write the failing test**

```python
# bootloader/tests/test_open_design.py
import unittest, tempfile, os
from unittest.mock import patch, MagicMock

class TestOpenDesign(unittest.TestCase):
    def setUp(self):
        self.user_home = tempfile.mkdtemp()
        self.context = {"USER_HOME": self.user_home}

    @patch("subprocess.run")
    def test_prereq_false_when_missing(self, mock_run):
        mock_run.return_value = MagicMock()
        import bootloader.plugins.open_design as od; import importlib; importlib.reload(od)
        mock_run.side_effect = FileNotFoundError()
        result = od.hook_check_prerequisites(self.context)
        self.assertFalse(result)

    @patch("subprocess.run")
    @patch("os.path.isdir")
    def test_install_idempotent(self, mock_isdir, mock_run):
        mock_isdir.side_effect = lambda p: "node_modules" in p
        mock_run.return_value = MagicMock(returncode=0)
        import bootloader.plugins.open_design as od; import importlib; importlib.reload(od)
        r1 = od.hook_install(self.context)
        r2 = od.hook_install(self.context)
        self.assertTrue(r1["installed"])
        self.assertTrue(r2.get("skipped", False))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest bootloader/tests/test_open_design.py -v`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```python
"""
Open Design Plugin

Clones and installs the Open Design web app.
"""

import os
import subprocess
from typing import Any, Dict


OPEN_DESIGN_REPO = "https://github.com/nousresearch/open-design.git"
INSTALL_DIR = "/srv/ai-stack/open-design"


def hook_check_prerequisites(context: Dict[str, Any]) -> bool:
    if os.path.isdir(INSTALL_DIR):
        print(f"Open Design already at {INSTALL_DIR}")
        return True
    print(f"Open Design not found at {INSTALL_DIR}")
    return False


def hook_install(context: Dict[str, Any]) -> Dict[str, Any]:
    print("Installing Open Design...")

    if not os.path.isdir(INSTALL_DIR):
        print(f"Cloning {OPEN_DESIGN_REPO} into {INSTALL_DIR}")
        os.makedirs(INSTALL_DIR, exist_ok=True)
        subprocess.run(["git", "clone", OPEN_DESIGN_REPO, INSTALL_DIR], check=True)
    else:
        print(f"Open Design dir exists, pulling latest...")
        subprocess.run(["git", "-C", INSTALL_DIR, "pull"], check=True)

    print("Installing Node dependencies with pnpm...")
    subprocess.run(
        ["pnpm", "--dir", INSTALL_DIR, "install"],
        check=True,
        capture_output=True,
    )

    node_modules = os.path.join(INSTALL_DIR, "node_modules")
    return {
        "installed": True,
        "install_path": INSTALL_DIR,
        "node_modules_present": os.path.isdir(node_modules),
    }


def hook_verify(context: Dict[str, Any]) -> bool:
    node_modules = os.path.join(INSTALL_DIR, "node_modules")
    if os.path.isdir(node_modules):
        print(f"Open Design node_modules verified at {node_modules}")
        return True
    raise RuntimeError(f"Open Design node_modules not found at {node_modules}")


def hook_cleanup(context: Dict[str, Any]) -> None:
    pass
```

- [ ] **Step 4: Run test to verify it passes**

- [ ] **Step 5: Commit**

---

## Task 5: `mempalace.py`

**Files:**
- Create: `bootloader/plugins/mempalace.py`

- [ ] **Step 1: Write test** (follow patterns from Tasks 1-4)
- [ ] **Step 2: Run test — should fail**
- [ ] **Step 3: Write implementation**

```python
"""
MemPalace Plugin

Clones MemPalace repository, creates venv, installs dependencies,
and generates a start.sh wrapper script.
"""

import os
import subprocess
import venv
from typing import Any, Dict


MEMPALACE_REPO = "https://github.com/nousresearch/MemPalace.git"


def hook_check_prerequisites(context: Dict[str, Any]) -> bool:
    user_home = context.get("USER_HOME", os.path.expanduser("~"))
    mp_dir = os.path.join(user_home, ".mempalace")
    if os.path.isdir(mp_dir):
        print(f"MemPalace already exists at {mp_dir}")
        return True
    print(f"MemPalace not found at {mp_dir}")
    return False


def hook_install(context: Dict[str, Any]) -> Dict[str, Any]:
    print("Installing MemPalace...")

    user_home = context.get("USER_HOME", os.path.expanduser("~"))
    mp_dir = os.path.join(user_home, ".mempalace")
    venv_dir = os.path.join(mp_dir, "venv")

    if not os.path.isdir(mp_dir):
        print(f"Cloning {MEMPALACE_REPO} into {mp_dir}")
        subprocess.run(["git", "clone", MEMPALACE_REPO, mp_dir], check=True)
    else:
        print(f"MemPalace dir exists, pulling latest...")
        subprocess.run(["git", "-C", mp_dir, "pull"], check=True)

    if not os.path.isdir(venv_dir):
        print(f"Creating virtual environment at {venv_dir}")
        venv.create(venv_dir, with_pip=True)

    python_path = os.path.join(venv_dir, "bin", "python")
    pip_path = os.path.join(venv_dir, "bin", "pip")

    print("Installing MemPalace dependencies...")
    result = subprocess.run(
        [pip_path, "install", "-e", ".[all]"],
        cwd=mp_dir,
        capture_output=True,
    )
    if result.returncode != 0:
        subprocess.run([pip_path, "install", "-e", "."], cwd=mp_dir, check=True)

    # Generate start.sh wrapper
    start_script = os.path.join(mp_dir, "start.sh")
    with open(start_script, "w") as f:
        f.write(f"""#!/usr/bin/env bash
cd ~/{".mempalace"} && {venv_dir}/bin/python -m mempacl "$@"
""")
    os.chmod(start_script, 0o755)

    return {
        "installed": True,
        "install_path": mp_dir,
        "venv_path": venv_dir,
        "start_script": start_script,
    }


def hook_verify(context: Dict[str, Any]) -> bool:
    user_home = context.get("USER_HOME", os.path.expanduser("~"))
    venv_dir = os.path.join(user_home, ".mempalace", "venv")
    python_path = os.path.join(venv_dir, "bin", "python")
    start_script = os.path.join(user_home, ".mempalace", "start.sh")

    if not os.path.isfile(python_path):
        raise RuntimeError(f"MemPalace venv python not found: {python_path}")
    if os.name != "nt" and not os.access(python_path, os.X_OK):
        raise RuntimeError(f"MemPalace venv python not executable: {python_path}")
    if not os.path.isfile(start_script):
        raise RuntimeError(f"MemPalace start.sh not found: {start_script}")
    print(f"MemPalace verified: {python_path}, start.sh: {start_script}")
    return True


def hook_cleanup(context: Dict[str, Any]) -> None:
    pass
```

- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Commit**

---

## Task 6: `systemd_services.py`

**Files:**
- Create: `bootloader/plugins/systemd_services.py`

- [ ] **Step 1: Write test**
- [ ] **Step 2: Run test — should fail**
- [ ] **Step 3: Write implementation** (see plan Section 3.6 for unit file content)
- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Commit**

---

## Task 7: `security_hardening.py`

**Files:**
- Create: `bootloader/plugins/security_hardening.py`

- [ ] **Step 1: Write test**
- [ ] **Step 2: Run test — should fail**
- [ ] **Step 3: Write implementation** — Key logic:
  - Recursively chmod 700 on `~/.hermes`, `~/.openclaw`, `~/.mempalace` directories
  - chmod 600 on `~/.hermes/config.yaml`, `~/.openclaw/config.yaml`
  - Check if `iptables` is available via `subprocess.run(["which", "iptables"], capture_output=True)` — if not found in WSL2, log and skip
  - On native Linux: flush existing rules, set default DROP, add allow rules
- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Commit**

---

## Task 8: `maintenance_scripts.py`

**Files:**
- Create: `bootloader/plugins/maintenance_scripts.py`

- [ ] **Step 1: Write test** — Verify: scripts exist, are executable, cron entry added
- [ ] **Step 2: Run test — should fail**
- [ ] **Step 3: Write implementation**
  - Write `~/.hermes/scripts/hermes-backup.sh`: tar.gz of sessions/state.db/snapshots, 7-day retention
  - Write `~/.hermes/scripts/hermes-health-check.sh`: check dirs and venvs exist
  - `chmod +x` both scripts
  - Programmatic crontab: read existing via `crontab -l`, add `@daily /home/lurkr/ai-platform/scripts/hermes-sync.sh` if not already present, write back via `crontab -`
- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Commit**

---

## Task 9: `bootstrap.sh`

**Files:**
- Create: `bootloader/bootstrap.sh`

- [ ] **Write the file**

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[bootstrap] Installing minimal system dependencies..."
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip git curl > /dev/null

cd "$SCRIPT_DIR"

echo "[bootstrap] Installing bootloader..."
pip install -e . --quiet --break-system-packages

echo "[bootstrap] Running bootloader..."
python3 -m bootloader.cli "$@"
```

- [ ] **Test bootstrap.sh runs without error** (on joBlade)
- [ ] **Commit**

---

## Task 10: `test_plugins.py`

**Files:**
- Create: `bootloader/tests/__init__.py`
- Create: `bootloader/tests/test_plugins.py`

The comprehensive test file covering all 8 plugins with:
- Mocked `subprocess.run`, `os.path.isdir`, `os.path.isfile`, `os.stat`, `os.chmod`, `os.makedirs`
- Per-plugin test for prereq pass/fail
- Per-plugin test for install idempotency (second run returns `skipped: True`)
- Per-plugin test for verify pass/fail
- Verify that `test_plugins.py` runs clean with `pytest -v` under Python 3.10, 3.11, 3.12

---

## Self-Review Checklist

- [ ] Every task has actual code in Step 3 (no TBD, no TODO, no "implement similar to X")
- [ ] Tests mock `subprocess.run` — no real network calls in CI
- [ ] All 8 plugins have `hook_cleanup` implemented (even if no-op)
- [ ] `security_hardening.py` gracefully skips iptables on WSL2 (no hard requirement)
- [ ] `openclaw_config.py` and `hermes_config.py` both preserve `allowed_users` on re-run
- [ ] After all 8 plugins, `python3 -m bootloader.cli install` completes with all `hook_verify` returning True