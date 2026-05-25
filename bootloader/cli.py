#!/usr/bin/env python3
"""Bootloader CLI for managing plugin-based system setup."""

import argparse
import json
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Import PluginManager and StateManager from the local lib package
from .lib.plugin_system import PluginManager
from .lib.state_manager import StateManager

# ANSI color codes
BLUE = '\033[0;34m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
RED = '\033[0;31m'
NC = '\033[0m'  # No Color

# State file path
STATE_FILE = Path.home() / ".hermes" / "bootloader-state.json"


def load_state() -> Dict[str, Any]:
    """Load bootloader state from disk or initialize if not exists."""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"{RED}Error loading state file: {e}{NC}", file=sys.stderr)
            # Fall back to empty state
            pass

    # Initialize fresh state with all plugins having all phases as False
    return {
        "plugins": {},
        "last_updated": datetime.utcnow().isoformat()
    }


def save_state_atomic(state: Dict[str, Any]) -> None:
    """Save state to disk atomically (write to temp then rename)."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp_path = STATE_FILE.with_suffix('.json.tmp')

    try:
        with open(temp_path, 'w') as f:
            json.dump(state, f, indent=2)
        temp_path.replace(STATE_FILE)
    except Exception as e:
        print(f"{RED}Error saving state file: {e}{NC}", file=sys.stderr)
        if temp_path.exists():
            temp_path.unlink()
        raise


def update_plugin_state(state: Dict[str, Any], plugin_name: str, phase: str, completed: bool = True) -> None:
    """Mark a phase as completed for a plugin and save state."""
    if plugin_name not in state["plugins"]:
        state["plugins"][plugin_name] = {
            "prereq": False,
            "install": False,
            "verify": False,
            "cleanup": False
        }
    state["plugins"][plugin_name][phase] = completed
    state["last_updated"] = datetime.utcnow().isoformat()
    save_state_atomic(state)


def get_plugins_for_phase(plugin_manager: PluginManager, state: Dict[str, Any], phase: str, force: bool) -> List[Tuple[str, Any]]:
    """Get list of (plugin_name, plugin) tuples that need to run the given phase."""
    plugins_to_run = []
    for plugin_name, plugin in sorted(plugin_manager.plugins.items()):
        # Check if phase is already completed
        plugin_state = state.get("plugins", {}).get(plugin_name, {})
        phase_completed = plugin_state.get(phase, False)

        if phase_completed and not force:
            # Skip already completed phase unless force
            continue

        # Check if plugin has the required hook
        hook_name = phase_to_hook(phase)
        if hook_name in plugin.hooks:
            plugins_to_run.append((plugin_name, plugin))
        else:
            # Plugin doesn't have this hook, skip but still mark as "done" if it was in progress?
            # For now, just skip silently
            pass

    return plugins_to_run


def phase_to_hook(phase: str) -> str:
    """Map phase name to hook function name."""
    mapping = {
        'prereq': 'check_prerequisites',
        'install': 'install',
        'verify': 'verify',
        'cleanup': 'cleanup'
    }
    return mapping[phase]


def run_phase(phase: str, plugins_to_run: List[Tuple[str, Any]], context: Dict[str, Any], dry_run: bool, state: Dict[str, Any]) -> Tuple[bool, int]:
    """
    Execute a phase for all specified plugins.

    Returns:
        (success, exit_code)
    """
    hook_name = phase_to_hook(phase)
    total = len(plugins_to_run)
    completed = 0
    failed = False

    print(f"\n{YELLOW}=== PHASE: {phase.upper()} ==={NC}")
    print(f"Phase: {phase} | Total plugins: {total}")

    if total == 0:
        print(f"{GREEN}All plugins already completed this phase (or no plugins to run).{NC}")
        return True, 0

    for plugin_name, plugin in plugins_to_run:
        if dry_run:
            print(f"  [DRY-RUN] Would run {hook_name} for {plugin_name}")
            completed += 1
            continue

        try:
            print(f"  [RUN] {hook_name} for {plugin_name}...", end="", flush=True)
            result = plugin.execute_hook(hook_name, context)

            # Handle result based on phase
            if phase == 'prereq':
                # result should be boolean; if any False, abort
                if result is False:
                    print(f" {RED}FAILED{NC}")
                    print(f"{RED}Prerequisite check failed for {plugin_name}. Aborting.{NC}")
                    failed = True
                    break
                else:
                    print(f" {GREEN}OK{NC}")
                    update_plugin_state(state, plugin_name, phase, True)
                    completed += 1

            elif phase == 'install':
                # Success, update state with returned changes
                print(f" {GREEN}OK{NC}")
                update_plugin_state(state, plugin_name, phase, True)
                completed += 1

            elif phase == 'verify':
                # result should be True; if not, abort
                if result is not True:
                    print(f" {RED}FAILED{NC}")
                    print(f"{RED}Verification failed for {plugin_name}. Aborting.{NC}")
                    failed = True
                    break
                else:
                    print(f" {GREEN}PASS{NC}")
                    update_plugin_state(state, plugin_name, phase, True)
                    completed += 1

            elif phase == 'cleanup':
                # Always run, success assumed unless exception
                print(f" {GREEN}DONE{NC}")
                update_plugin_state(state, plugin_name, phase, True)
                completed += 1

        except Exception as e:
            print(f" {RED}ERROR{NC}")
            print(f"{RED}Error executing {hook_name} for {plugin_name}:{NC}")
            traceback.print_exc()
            failed = True
            break

    # Summary
    print(f"{GREEN}Completed {completed}/{total} plugins{NC}")
    if failed:
        print(f"{RED}Phase '{phase}' failed. Aborting further execution for this phase.{NC}")
        return False, 1

    return True, 0


def print_header() -> None:
    """Print bootloader header."""
    now = datetime.utcnow().isoformat() + 'Z'
    print(f"{BLUE}Bootloader v1.0{NC}")
    print(f"Timestamp: {now}")
    print(f"State file: {STATE_FILE}")


def run_bootloader(args: argparse.Namespace, plugin_manager: PluginManager) -> int:
    """Execute the bootloader phases with real hook execution and state tracking."""
    print_header()

    # Load state
    state = load_state()
    print(f"State loaded: {len(state.get('plugins', {}))} plugin(s) with previous progress")

    # Determine which phases to run
    if args.phase == 'all':
        phases = ['prereq', 'install', 'verify', 'cleanup']
    else:
        phases = [args.phase]

    # Prepare context dict for hooks
    context: Dict[str, Any] = {
        'USER_HOME': str(Path.home()),
        'dry_run': args.dry_run,
        'state': state,
        'verbose': True  # Could be controlled by a flag if needed
    }

    # Snapshot/restore handling (scaffolding)
    if args.restore:
        # Restore snapshot before execution
        print(f"{YELLOW}Restoring snapshot: {args.restore}{NC}")
        hermes_state_dir = Path.home() / ".hermes"
        snapshots_dir = hermes_state_dir / "snapshots"
        snapshot_file = snapshots_dir / f"{args.restore}.json"
        if snapshot_file.exists():
            try:
                with open(snapshot_file, 'r') as f:
                    snapshot_data = json.load(f)
                print(f"Snapshot loaded from: {snapshot_file}")
                print(f"Snapshot timestamp: {snapshot_data.get('metadata', {}).get('timestamp', 'unknown')}")
                print(f"{YELLOW}[NOTE] Snapshot restore is currently just scaffolding - state not actually restored to system.{NC}")
            except Exception as e:
                print(f"{RED}Error loading snapshot: {e}{NC}")
                return 1
        else:
            print(f"{RED}Snapshot not found: {snapshot_file}{NC}")
            return 1

    # Main phase execution loop
    overall_success = True
    final_exit_code = 0

    for phase in phases:
        print(f"\n{BLUE}Preparing to run phase: {phase}{NC}")

        # Snapshot before install (if requested)
        if args.snapshot and phase == 'install':
            print(f"{YELLOW}Capturing snapshot: {args.snapshot}{NC}")
            try:
                hermes_state_dir = Path.home() / ".hermes"
                sm = StateManager(hermes_state_dir)
                snapshot = sm.capture_snapshot(args.snapshot)
                saved_path = sm.save_snapshot(snapshot)
                print(f"{GREEN}Snapshot saved to: {saved_path}{NC}")
                print(f"{YELLOW}[NOTE] Snapshot capture is scaffolding - not affecting state restore logic.{NC}")
            except Exception as e:
                print(f"{RED}Error capturing snapshot: {e}{NC}")
                # Continue execution

        # Get plugins that need to run this phase
        plugins_to_run = get_plugins_for_phase(plugin_manager, state, phase, args.force)

        if not plugins_to_run:
            if args.dry_run:
                print(f"\n{YELLOW}=== PHASE: {phase.upper()} ==={NC}")
                print(f"  [DRY-RUN] No plugins need to run (all already completed or missing hooks)")
            else:
                print(f"{GREEN}No plugins need to run phase '{phase}' (all already completed).{NC}")
            continue

        # Run phase for these plugins
        success, exit_code = run_phase(phase, plugins_to_run, context, args.dry_run, state)
        if not success:
            overall_success = False
            final_exit_code = exit_code
            # For prereq and verify, we abort only that phase and continue? The spec says "stop further plugins for that phase"
            # But we should probably stop all subsequent phases as well if a critical phase fails?
            # Based on spec: "If a phase fails (False from verify or exception from install), stop further plugins for that phase and report error."
            # It doesn't say to stop subsequent phases, but logically if prereq or install fails, you shouldn't continue.
            # Let's break out of the phase loop on failure for safety, except maybe cleanup should still run?
            # However, the specification says "stop further plugins for that phase" not "stop all phases".
            # To be safe, I'll implement: break on phase failure, don't run remaining phases.
            break

    # Final summary
    print(f"\n{BLUE}=== BOOTLOADER COMPLETE ==={NC}")
    if overall_success:
        print(f"{GREEN}All phases completed successfully.{NC}")
    else:
        print(f"{RED}Bootloader completed with errors.{NC}")

    return final_exit_code


def list_plugins(plugin_manager: PluginManager) -> None:
    """List discovered plugins and their hook status."""
    print(f"{BLUE}=== Bootloader Plugins ==={NC}")
    if not plugin_manager.plugins:
        print(f"{YELLOW}No plugins discovered.{NC}")
        return

    state = load_state()
    for name, plugin in sorted(plugin_manager.plugins.items()):
        hooks = list(plugin.hooks.keys())
        pstate = state.get("plugins", {}).get(name, {})
        status_parts = []
        for phase in ['prereq', 'install', 'verify', 'cleanup']:
            if pstate.get(phase):
                status_parts.append(f"{GREEN}{phase}{NC}")
            else:
                status_parts.append(f"{YELLOW}{phase}{NC}")
        print(f"  {BLUE}{name}{NC}: {', '.join(status_parts)}")
        print(f"    hooks: {', '.join(hooks)}")
    print(f"{BLUE}==========================={NC}")


def main() -> int:
    # Set up argument parser
    parser = argparse.ArgumentParser(
        description="Bootloader CLI for plugin-based system setup."
    )

    # Optional command: defaults to 'run' if omitted
    parser.add_argument('command', nargs='?', choices=['list', 'run'],
                        help='Command to execute (default: run)')

    # Run-specific options (used when command is 'run' or default)
    parser.add_argument('--phase', choices=['prereq', 'install', 'verify', 'cleanup', 'all'],
                        default='all', help='Bootloader phase to run (default: all)')
    parser.add_argument('--force', action='store_true',
                        help='Force re-execution of phases even if already completed')
    parser.add_argument('--dry-run', action='store_true',
                        help='Print actions without executing')
    parser.add_argument('--snapshot', type=str, metavar='NAME',
                        help='Create a snapshot before install phase')
    parser.add_argument('--restore', type=str, metavar='SNAPSHOT_NAME',
                        help='Restore state before running')

    args = parser.parse_args()

    # Initialize plugin system
    plugin_dir = Path(__file__).parent / "plugins"
    plugin_manager = PluginManager(plugin_dir)
    discovered = plugin_manager.discover_plugins()

    # Execute the requested command
    if args.command == 'list':
        list_plugins(plugin_manager)
    else:
        exit_code = run_bootloader(args, plugin_manager)
        return exit_code

    return 0


if __name__ == "__main__":
    sys.exit(main())
