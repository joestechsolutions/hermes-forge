# Bootloader Architecture

## Purpose

The Bootloader provides a repeatable, idempotent, and recoverable provisioning process for the Hermes Agent infrastructure. It can restore the entire stack on a fresh Linux machine, capture state snapshots before changes, and roll back if needed.

## Components

- **StateManager** (`lib/state_manager.py`): Handles snapshots of system state (configs, services, data) and backup/restore operations. Stores snapshots as JSON in `~/.hermes/snapshots/`.
- **PluginManager** (`lib/plugin_system.py`): Discovers plugins in `plugins/`, orchestrates execution of hook phases: `check_prerequisites`, `install`, `verify`, `cleanup`. Tracks per-plugin state in `~/.hermes/bootloader-state.json` to enable resume and idempotency.
- **CLI** (`cli.py`): Entrypoint invoked by `bootloader.sh`. Supports commands:
  - `list` – show discovered plugins and their statuses
  - `run` – execute one or more phases with options:
    - `--phase <prereq|install|verify|cleanup|all>` (default all)
    - `--dry-run` – print actions without execution
    - `--force` – re-run phases even if already completed
    - `--snapshot <NAME>` – capture snapshot before install phase
    - `--restore <SNAPSHOT>` – restore state before running

## Plugins

Each plugin encapsulates an installation or maintenance step. Example plugins:

- `system_deps`: apt packages
- `nodejs`: NodeSource setup, install nodejs & npm
- `docker`: Docker apt repo, install docker.io, start/enable
- `ollama`: Install and configure Ollama service, pull default model
- `gitnexus`: Build and install GitNexus binary
- `directories`: Create required dirs (`~/.hermes`, `~/jcode`, etc.)
- `hermes_agent`: Clone/update Hermes Agent, install Python deps, setup systemd services (telegram, gateway)
- `hermes_config`: Deploy config files and environment templates
- `dashboard`: install dashboard backend & frontend, enable service

Plugins are automatically discovered and run in alphabetical order. Ensure naming respects dependencies (e.g., `system_deps` before `nodejs`).

## State Tracking

The bootloader maintains `~/.hermes/bootloader-state.json`. For each plugin it records whether a phase has completed:

```json
{
  "plugins": {
    "system_deps": {"prereq": true, "install": true, "verify": true, "cleanup": false},
    ...
  },
  "last_updated": "2026-05-10T22:30:00Z"
}
```

State is updated atomically after each successful phase. Subsequent runs skip phases that are already done unless `--force` is used.

## Snapshots

Snapshots capture the full system state before major changes. They include:
- All critical config files (Hermes, OpenClaw, OpenCode, MemPalace)
- Service status (enabled/disabled)
- Docker volumes and images (optional)
- Bootloader state

Use `--snapshot NAME` during `run` to create a snapshot automatically before `install` phase. Snapshots are stored in `~/.hermes/snapshots/`.

## Integration with Hermes

After the bootloader completes installation, Hermes Agent is fully functional. Snapshots can also be managed through the Hermes CLI or the Dashboard.

## Extending

To add a new plugin:
1. Create a new file in `plugins/`, e.g., `myplugin.py`.
2. Define a class inheriting from `BootloaderPlugin`. Set `name = "myplugin"`.
3. Implement hook methods as `async def install(self, context)`, etc.
4. Use `context` to access `dry_run`, `state`, and home directory.
5. Make operations idempotent (safe to re-run).
6. The next bootloader run will discover and execute it.

## Error Handling & Rollback

If a phase fails (returns `False` or raises), the bootloader aborts the current phase loop. The `cleanup` hook is designed to undo partial changes if needed. The state file records only completed phases, allowing safe resume after fixing errors. Full system rollback is achieved by restoring a snapshot via `StateManager`.

## Bootstrapping

`bootloader.sh` is the initial entrypoint. It first attempts to import the Python CLI (module `bootloader.cli`). If available, it delegates to it. Otherwise it falls back to its built-in bash installation logic (used only on very first run). Initially, the bootloader must be obtained via `curl` or git clone. Subsequent runs use the plugin CLI.
