"""
StateManager for bootloader snapshots.

Provides functionality to capture, save, list, and restore system state snapshots
including services, configurations, models, docker containers, and directory metrics.
"""

import base64
import json
import hashlib
import datetime
import os
import pathlib
import subprocess
import sys
import shutil
from typing import Dict, List, Any, Optional

from bootloader.lib.platform import system_data_dir, service_reload


class StateManager:
    """
    Manages system state snapshots for the bootloader.

    Attributes:
        state_dir (Path): Base directory for storing snapshots
        snapshots_dir (Path): Subdirectory for snapshot files
        backups_dir (Path): Subdirectory for .backup-*/ pre-change archives
    """

    _SYSTEM_DATA_DIR = pathlib.Path(system_data_dir(pathlib.Path.home()))

    CRITICAL_CONFIGS = [
        str(pathlib.Path.home() / ".hermes/config.yaml"),
        str(pathlib.Path.home() / ".hermes/.env"),
        str(pathlib.Path.home() / ".openclaw/openclaw.json"),
        str(pathlib.Path.home() / ".opencode/opencode.json"),
        str(pathlib.Path.home() / ".mempalace/config.json"),
        str(_SYSTEM_DATA_DIR / "docker-compose.yml"),
        str(_SYSTEM_DATA_DIR / ".env"),
    ]

    CRITICAL_DIRS = [
        str(pathlib.Path.home() / ".hermes"),
        str(pathlib.Path.home() / ".openclaw"),
        str(pathlib.Path.home() / ".opencode"),
        str(pathlib.Path.home() / ".mempalace"),
        str(_SYSTEM_DATA_DIR),
    ]

    def __init__(self, state_dir: pathlib.Path) -> None:
        """
        Initialize StateManager with a base state directory.

        Args:
            state_dir: Directory to store snapshot data; 'snapshots' and 'snapshots/backups' subdirectories created
        """
        self.state_dir = state_dir.resolve()
        self.snapshots_dir = self.state_dir / "snapshots"
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        self.backups_dir = self.snapshots_dir / "backups"
        self.backups_dir.mkdir(parents=True, exist_ok=True)

    def _run_command(self, cmd: List[str], default: Any = None) -> Any:
        """
        Run a subprocess command and return parsed JSON output.

        Args:
            cmd: Command to execute as list of strings
            default: Value to return on failure

        Returns:
            Parsed JSON data or default value on error
        """
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            if result.returncode == 0 and result.stdout.strip():
                return json.loads(result.stdout)
        except Exception as e:
            print(f"Command failed: {' '.join(cmd)}: {e}", file=sys.stderr)
        return default

    def _compute_sha256(self, filepath: str) -> Optional[str]:
        """
        Compute SHA256 hash of a file.

        Args:
            filepath: Path to the file

        Returns:
            Hexadecimal digest string or None on failure
        """
        try:
            with open(filepath, "rb") as f:
                return hashlib.sha256(f.read()).hexdigest()
        except Exception as e:
            print(f"Failed to hash {filepath}: {e}", file=sys.stderr)
            return None

    def _get_directory_stats(self, dirpath: str) -> Optional[Dict[str, Any]]:
        """
        Compute size and modification time for a directory.

        Args:
            dirpath: Directory path

        Returns:
            Dict with 'size' (total bytes) and 'modified' (ISO8601 timestamp) or None
        """
        try:
            p = pathlib.Path(dirpath)
            if not p.exists():
                return None
            total_size = 0
            latest_mtime = 0
            for file in p.rglob("*"):
                if file.is_file():
                    try:
                        total_size += file.stat().st_size
                        latest_mtime = max(latest_mtime, file.stat().st_mtime)
                    except OSError:
                        continue
            return {
                "size": total_size,
                "modified": (
                    datetime.datetime.fromtimestamp(
                        latest_mtime, tz=datetime.timezone.utc
                    ).isoformat()
                    if latest_mtime > 0
                    else None
                ),
            }
        except Exception as e:
            print(f"Failed to stat directory {dirpath}: {e}", file=sys.stderr)
            return None

    def _read_config_content(self, filepath: str) -> Optional[Dict[str, Any]]:
        """
        Read config file and return its content + hash for snapshot storage.

        Args:
            filepath: Path to the config file

        Returns:
            Dict with 'content' (base64-encoded for binary safety) and 'hash', or None
        """
        try:
            with open(filepath, "rb") as f:
                data = f.read()
            return {
                "content": base64.b64encode(data).decode("ascii"),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        except Exception as e:
            print(f"Failed to read config {filepath}: {e}", file=sys.stderr)
            return None

    def capture_snapshot(self, name: Optional[str] = None) -> Dict[str, Any]:
        """
        Capture a complete system state snapshot.

        Config files are stored with their full base64-encoded content so they
        can be fully restored, not just verified by hash.

        Args:
            name: Optional name identifier for the snapshot

        Returns:
            Dictionary containing all snapshot data
        """
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        version = "1.0"

        # Services
        if sys.platform == 'darwin':
            # macOS: list launchd jobs matching com.hermes
            try:
                result = subprocess.run(
                    ["launchctl", "list"],
                    capture_output=True, text=True, check=False, timeout=30,
                )
                services = []
                if result.returncode == 0:
                    for line in result.stdout.strip().split('\n'):
                        parts = line.split()
                        if len(parts) >= 3 and 'com.hermes' in parts[2]:
                            services.append({
                                "UnitName": parts[2],
                                "ActiveState": "active" if parts[0] != '-' else "inactive",
                                "SubState": parts[0] if parts[0] != '-' else "",
                                "Description": parts[2],
                            })
            except Exception as e:
                print(f"Failed to list launchd jobs: {e}", file=sys.stderr)
                services = []
        else:
            # Linux: systemctl user units
            services = self._run_command(
                ["systemctl", "--user", "list-units", "--type=service", "--all", "--output=json"],
                default=[],
            )

        # Config file content + hashes (stored for restore)
        configs: Dict[str, Optional[Dict[str, Any]]] = {}
        for config_path in self.CRITICAL_CONFIGS:
            if pathlib.Path(config_path).is_file():
                configs[config_path] = self._read_config_content(config_path)
            else:
                configs[config_path] = None

        # Ollama models
        models = self._run_command(["ollama", "list"], default=[])

        # Docker containers
        docker = self._run_command(["docker", "ps", "-a", "--format", "json"], default={})
        if isinstance(docker, dict):
            docker = [docker]

        # Directory stats
        directories: Dict[str, Optional[Dict[str, Any]]] = {}
        for dir_path in self.CRITICAL_DIRS:
            directories[dir_path] = self._get_directory_stats(dir_path)

        snapshot = {
            "metadata": {
                "timestamp": timestamp,
                "name": name,
                "version": version,
            },
            "services": services,
            "configs": configs,
            "models": models,
            "docker": docker,
            "directories": directories,
        }

        return snapshot

    def save_snapshot(self, snapshot: Dict[str, Any], path: Optional[pathlib.Path] = None) -> pathlib.Path:
        """
        Save a snapshot to disk as JSON.

        Args:
            snapshot: Snapshot dictionary to save
            path: Optional full path; if None, auto-generate in snapshots_dir

        Returns:
            Path object to the saved file
        """
        if path is None:
            ts = snapshot["metadata"]["timestamp"]
            safe_ts = ts.replace(":", "-").replace(".", "-").replace("+", "-")
            snapshot_name = snapshot["metadata"].get("name") or "snapshot"
            safe_name = snapshot_name.replace(" ", "-").replace("/", "-")
            filename = f"{safe_ts}_{safe_name}.json"
            path = self.snapshots_dir / filename

        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(snapshot, f, indent=2)
        return path

    def list_snapshots(self) -> List[Dict[str, Any]]:
        """
        List all available snapshots sorted by timestamp descending.

        Returns:
            List of dicts with keys: 'name', 'timestamp', 'file'
        """
        snapshots = []
        try:
            for entry in self.snapshots_dir.iterdir():
                if entry.is_file() and entry.suffix == ".json":
                    try:
                        with open(entry, "r") as f:
                            data = json.load(f)
                        meta = data.get("metadata", {})
                        snapshots.append(
                            {
                                "name": meta.get("name", entry.stem),
                                "timestamp": meta.get("timestamp", ""),
                                "file": str(entry),
                            }
                        )
                    except Exception:
                        continue
        except OSError:
            pass

        snapshots.sort(key=lambda x: x["timestamp"], reverse=True)
        return snapshots

    def load_snapshot(self, snapshot_path: pathlib.Path) -> Optional[Dict[str, Any]]:
        """
        Load a snapshot file from disk.

        Args:
            snapshot_path: Path to the snapshot JSON file

        Returns:
            Snapshot dict or None on failure
        """
        try:
            with open(snapshot_path, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load snapshot {snapshot_path}: {e}", file=sys.stderr)
            return None

    def apply_snapshot(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """
        Restore system state from a snapshot.

        Performs a backup of current configs before overwriting,
        then writes config file content from the snapshot and
        restores systemd service states to match the snapshot.

        Args:
            snapshot: Snapshot dict loaded via load_snapshot()

        Returns:
            Dict with 'restored_configs', 'restored_services', 'errors'
        """
        user_home = pathlib.Path.home()
        results: Dict[str, Any] = {
            "restored_configs": [],
            "restored_services": [],
            "errors": [],
            "backups": [],
        }

        # Create a backup timestamp dir for this restore operation
        restore_ts = datetime.datetime.now(datetime.timezone.utc).isoformat().replace(":", "-")
        restore_backup_dir = self.backups_dir / f"restore-{restore_ts}"
        restore_backup_dir.mkdir(parents=True, exist_ok=True)

        # Restore config files
        configs = snapshot.get("configs", {})
        for config_path_str, config_data in configs.items():
            if config_data is None:
                continue
            config_path = pathlib.Path(config_path_str)
            if not config_path.is_file():
                continue

            # Backup current config first
            try:
                backup_path = restore_backup_dir / config_path.name
                shutil.copy2(config_path, backup_path)
                results["backups"].append(str(backup_path))
            except Exception as e:
                results["errors"].append(f"Backup failed for {config_path}: {e}")
                continue

            # Decode and write content
            try:
                content_bytes = base64.b64decode(config_data["content"])
                written_hash = hashlib.sha256(content_bytes).hexdigest()
                if written_hash != config_data["sha256"]:
                    results["errors"].append(
                        f"Hash mismatch after decode for {config_path}; refusing to write"
                    )
                    continue
                config_path.parent.mkdir(parents=True, exist_ok=True)
                with open(config_path, "wb") as f:
                    f.write(content_bytes)
                results["restored_configs"].append(config_path_str)
            except Exception as e:
                results["errors"].append(f"Failed to restore {config_path}: {e}")

        # Restore service states (systemd on Linux, launchd on macOS)
        services = snapshot.get("services", [])
        if isinstance(services, list):
            if sys.platform == 'darwin':
                # macOS: use launchctl to manage com.hermes services
                for svc_data in services:
                    unit_name = svc_data.get("UnitName") or svc_data.get("name")
                    active_state = svc_data.get("ActiveState", "")
                    if not unit_name:
                        continue
                    known_services = {"hermes-gateway", "openclaw-gateway", "open-design", "dashboard-backend"}
                    if unit_name not in known_services:
                        continue
                    try:
                        if active_state in ("active", "activating"):
                            subprocess.run(
                                ["launchctl", "kickstart", f"gui/{os.getuid()}/{unit_name}"],
                                capture_output=True, check=False,
                            )
                        elif active_state in ("inactive", "deactivating", "failed"):
                            subprocess.run(
                                ["launchctl", "bootout", f"gui/{os.getuid()}/{unit_name}"],
                                capture_output=True, check=False,
                            )
                        results["restored_services"].append(unit_name)
                    except Exception as e:
                        results["errors"].append(f"Service {unit_name} restore failed: {e}")
            else:
                # Linux: systemctl user units
                for svc_data in services:
                    unit_name = svc_data.get("UnitName") or svc_data.get("name")
                    active_state = svc_data.get("ActiveState", "")
                    if not unit_name:
                        continue
                    # Only restore state for known services that we manage
                    known_services = {"hermes-gateway", "openclaw-gateway", "open-design", "dashboard-backend"}
                    if unit_name not in known_services:
                        continue
                    try:
                        if active_state in ("active", "activating"):
                            subprocess.run(
                                ["systemctl", "--user", "start", unit_name],
                                capture_output=True,
                                check=False,
                            )
                            subprocess.run(
                                ["systemctl", "--user", "enable", unit_name],
                                capture_output=True,
                                check=False,
                            )
                        elif active_state in ("inactive", "deactivating", "failed"):
                            subprocess.run(
                                ["systemctl", "--user", "stop", unit_name],
                                capture_output=True,
                                check=False,
                            )
                        results["restored_services"].append(unit_name)
                    except Exception as e:
                        results["errors"].append(f"Service {unit_name} restore failed: {e}")

        # Reload service manager after changes
        if sys.platform != 'darwin':
            try:
                service_reload()
            except Exception:
                pass

        return results


def main() -> int:
    """Standalone test when executed directly."""
    try:
        sm = StateManager(pathlib.Path.home() / ".hermes")
        snapshot = sm.capture_snapshot("test-snapshot")
        path = sm.save_snapshot(snapshot)
        print(f"Saved to {path}")
        print(f"Has services: {len(snapshot.get('services', []))}")
        print(f"Available snapshots: {len(sm.list_snapshots())}")

        # Test loading and applying
        loaded = sm.load_snapshot(path)
        if loaded:
            results = sm.apply_snapshot(loaded)
            print(f"Restore would restore {len(results['restored_configs'])} configs")
            print(f"Restore errors: {len(results['errors'])}")

        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())