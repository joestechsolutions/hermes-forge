"""
Maintenance Scripts Plugin

Installs backup and health-check scripts into ~/.hermes/scripts/,
and sets up the @daily cron entry for hermes-sync.
"""

import os
import subprocess
from typing import Any, Dict


SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERMES_SYNC_PATH = os.path.join(SCRIPT_DIR, "scripts", "hermes-sync.sh")


BACKUP_SCRIPT = """#!/usr/bin/env bash
#
# hermes-backup.sh — Backup Hermes state files
# Run manually or via cron
#
set -euo pipefail

HERMES_HOME="${HOME}/.hermes"
BACKUP_DIR="${HERMES_HOME}/backups"
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
BACKUP_FILE="${BACKUP_DIR}/hermes_backup_${TIMESTAMP}.tar.gz"

# Colors
GREEN='\\033[0;32m'
YELLOW='\\033[0;33m'
NC='\\033[0m'

log_info()  { echo -e "${GREEN}[backup]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[warn]${NC} $*" >&2; }

mkdir -p "$BACKUP_DIR"

log_info "Creating backup: $BACKUP_FILE"

# Build list of directories/files to back up
BACKUP_ITEMS=""
for item in sessions state.db response_store.db snapshots config.yaml .env; do
    path="${HERMES_HOME}/${item}"
    if [ -e "$path" ]; then
        BACKUP_ITEMS="${BACKUP_ITEMS} ${item}"
    else
        log_warn "Skipping missing item: ${item}"
    fi
done

tar -czf "$BACKUP_FILE" \\
    -C "$HERMES_HOME" \\
    ${BACKUP_ITEMS} \\
    2>/dev/null || true

# Clean up backups older than 7 days
find "$BACKUP_DIR" -name "hermes_backup_*.tar.gz" -mtime +7 -delete 2>/dev/null || true

# Report backup size
if [ -f "$BACKUP_FILE" ]; then
    SIZE=$(du -sh "$BACKUP_FILE" | cut -f1)
    log_info "Done: $BACKUP_FILE (${SIZE})"
else
    log_warn "Backup failed — no file created"
    exit 1
fi

log_info "Backups retained for 7 days."
"""


def hook_check_prerequisites(context: Dict[str, Any]) -> bool:
    """
    Verify the plugin can proceed. Returns False only if there's a hard
    blocker (e.g. source script missing). Otherwise returns True — install
    handles idempotency and skip logic.
    """
    if not os.path.isfile(HERMES_SYNC_PATH):
        print("hermes-sync.sh not found — cannot install maintenance scripts.")
        return False

    user_home = context.get("USER_HOME", os.path.expanduser("~"))
    scripts_dir = os.path.join(user_home, ".hermes", "scripts")
    backup_script = os.path.join(scripts_dir, "hermes-backup.sh")

    if os.path.isfile(backup_script) and os.access(backup_script, os.X_OK):
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        if HERMES_SYNC_PATH in result.stdout:
            print("Maintenance scripts already fully installed (script + cron).")
            return True
        print("Backup script exists but cron entry missing — will add cron.")
        return True

    print("Maintenance scripts not yet installed — will install.")
    return True


def hook_install(context: Dict[str, Any]) -> Dict[str, Any]:
    print("Installing maintenance scripts...")

    user_home = context.get("USER_HOME", os.path.expanduser("~"))
    scripts_dir = os.path.join(user_home, ".hermes", "scripts")
    os.makedirs(scripts_dir, exist_ok=True)

    # Write backup script
    backup_path = os.path.join(scripts_dir, "hermes-backup.sh")
    if not os.path.isfile(backup_path):
        with open(backup_path, "w") as f:
            f.write(BACKUP_SCRIPT)
        os.chmod(backup_path, 0o755)
        print(f"Created {backup_path}")
    else:
        print(f"Backup script already exists at {backup_path}")

    # Copy/symlink hermes-sync.sh into scripts dir (for cron reference)
    sync_dest = os.path.join(scripts_dir, "hermes-sync.sh")
    if os.path.isfile(HERMES_SYNC_PATH):
        if not os.path.islink(sync_dest) and not os.path.exists(sync_dest):
            os.symlink(HERMES_SYNC_PATH, sync_dest)

    # Add cron entry for hermes-sync
    cron_line = f"@daily {HERMES_SYNC_PATH}\n"
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    existing_cron = result.stdout if result.returncode == 0 else ""

    if cron_line.strip() not in existing_cron:
        new_cron = existing_cron + cron_line
        proc = subprocess.run(["crontab", "-"], input=new_cron, text=True, capture_output=True)
        if proc.returncode == 0:
            print(f"Added cron entry: {cron_line.strip()}")
        else:
            print(f"Warning: could not add cron entry: {proc.stderr}")
    else:
        print("Cron entry already exists — skipping.")

    return {
        "installed": True,
        "scripts_dir": scripts_dir,
        "backup_script": backup_path,
        "sync_script": HERMES_SYNC_PATH,
    }


def hook_verify(context: Dict[str, Any]) -> bool:
    user_home = context.get("USER_HOME", os.path.expanduser("~"))
    scripts_dir = os.path.join(user_home, ".hermes", "scripts")

    errors = []
    backup_path = os.path.join(scripts_dir, "hermes-backup.sh")

    if not os.path.isfile(backup_path):
        errors.append(f"Backup script not found at {backup_path}")
    elif not os.access(backup_path, os.X_OK):
        errors.append(f"Backup script is not executable: {backup_path}")

    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    cron_content = result.stdout if result.returncode == 0 else ""
    if HERMES_SYNC_PATH not in cron_content:
        errors.append("Cron entry for hermes-sync not found")

    if errors:
        raise RuntimeError(f"Maintenance scripts verification failed: {'; '.join(errors)}")
    print("Maintenance scripts verified successfully.")
    return True


def hook_cleanup(context: Dict[str, Any]) -> None:
    print("Removing maintenance scripts cron entry...")
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    if result.returncode != 0:
        return
    lines = [line for line in result.stdout.splitlines() if HERMES_SYNC_PATH not in line]
    new_cron = "\n".join(lines) + "\n"
    if new_cron.strip():
        subprocess.run(["crontab", "-"], input=new_cron, text=True, capture_output=True)
    else:
        subprocess.run(["crontab", "-r"], capture_output=True)
    print("Cron entry removed.")