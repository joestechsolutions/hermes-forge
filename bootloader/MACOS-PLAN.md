# Hermes Forge — macOS Support (IMPLEMENTED ✅)

**Status:** Phase 1 + Phase 2 complete. Phase 3 (full testing) pending.

## Architecture

```
lib/
├── platform/                       ← NEW: Platform abstraction layer
│   ├── __init__.py                 ← PlatformDetector, path helpers, adapter proxies
│   ├── linux.py                    ← Linux: apt, systemd, iptables
│   ├── darwin.py                   ← macOS: brew, launchctl, pfctl
│   └── plist_gen.py                ← Launchd plist XML generator
├── plugin_system.py                ← Updated: injects sys.path for plugin imports
├── state_manager.py                ← Updated: launchctl support, /srv → system_data_dir()
└── ...
```

## OS-by-OS Plugin Support

| Plugin | Linux | macOS | Notes |
|--------|-------|-------|-------|
| bootstrap.sh | ✅ apt | ✅ brew + auto-install | OS detection at top |
| system_deps | ✅ apt | ✅ brew | Shared via platform layer |
| nodejs | ✅ NodeSource | ✅ brew node@22 | Keg-only → brew link |
| pnpm | ✅ corepack | ✅ corepack | Cross-platform |
| gitnexus | ✅ npm i -g | ✅ npm i -g | Cross-platform |
| docker | ✅ install.sh | ✅ install.sh (cross-platform script) | Only usermod differs |
| ollama | ✅ systemctl | ✅ brew services + zshrc | OLLAMA_HOST config |
| hermes_agent | ✅ pip install | ✅ pip install | Already had os.name check |
| hermes_config | ✅ Path.home() | ✅ Path.home() | Cross-platform |
| mempalace | ✅ uv | ✅ uv | Cross-platform |
| openclaw | ✅ npm binary | ✅ npm binary | Already had os.name check |
| openclaw_config | ✅ yaml | ✅ yaml | Cross-platform |
| directories | ✅ /srv/ai-stack (sudo) | ✅ /usr/local/var/ai-stack | Uses system_data_dir() |
| security_hardening | ✅ iptables | ✅ pfctl or graceful skip | Uses firewall adapter |
| systemd_services | ✅ systemd | ✅ launchd plists | Uses plist_gen + service adapter |
| dashboard | ✅ systemd service | ⚠️ skip (no launchd yet) | Deploy only, no service |
| maintenance_scripts | ✅ crontab | ✅ crontab | macOS has crontab |
| open_design | ✅ /srv/ai-stack | ✅ /usr/local/var/ai-stack | Uses system_data_dir() |
| hermes-health.sh | ✅ systemd + ss | ✅ lsof + pfctl | OS detection in script |

## Key Decisions

1. **No separate macOS plugin files** — Single plugins with `if IS_MACOS:` branches (DRY, maintainable)
2. **`system_data_dir()` abstracts path** — resolves to `/srv/ai-stack` on Linux, `/usr/local/var/ai-stack` on macOS
3. **`service_*()` functions abstract service management** — systemctl vs launchctl/brew services
4. **`firewall_apply_hardening()`** — iptables vs pfctl
5. **bootstrap.sh auto-detects OS** — no separate install scripts needed
6. **Dashboard launchd integration deferred** — complex service definition; basic launchd support exists for core services

## Path Differences

| Purpose | Linux | macOS |
|---------|-------|-------|
| System data | `/srv/ai-stack` | `/usr/local/var/ai-stack` |
| User config | `~/.hermes/` | `~/.hermes/` (same) |
| Service configs | `~/.config/systemd/user/` | `~/Library/LaunchAgents/` |
| Node binaries | `~/.hermes/node/bin/` | `~/Library/Application Support/hermes/bin/` |

## Command Equivalents

| Action | Linux | macOS |
|--------|-------|-------|
| Install package | `apt-get install -y pkg` | `brew install pkg` |
| Restart service | `systemctl --user restart svc` | `brew services restart svc` |
| View logs | `journalctl --user -u svc` | `log show --predicate '...'` |
| List services | `systemctl --user list-units` | `brew services list` |
| Enable on boot | `systemctl --user enable svc` | `launchctl load -w plist` |
| Firewall rules | `iptables -A INPUT ...` | `pfctl -a anchor -f conf` |
| Code signing | N/A | `codesign -s - binary` |
| Health check | `stat -c '%a' file` | `stat -f '%A' file` |
| Listening ports | `ss -tlnp` | `lsof -iTCP -sTCP:LISTEN` |