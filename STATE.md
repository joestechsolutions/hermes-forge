# AI Agent Stack - State

**Date:** 2026-05-05
**Host:** joBlade (WSL2)

## Current Service Status

| Service | Port | Bind | Status | Method |
|---------|------|------|--------|--------|
| Ollama | 11434 | 127.0.0.1 | ✅ Running | systemd (system) |
| OpenWebUI | 3000 | 127.0.0.1 | ✅ Healthy | Docker |
| Hermes Gateway | 8642 | 127.0.0.1 | ✅ Running | systemd (user) |
| - Telegram | - | - | ✅ Connected | - |
| - API Server | - | - | ✅ Connected | - |
| Open Design Daemon | 7457 | 127.0.0.1 | ✅ Running | systemd (user) |
| Open Design Web | 4000 | 127.0.0.1 | ✅ Running | systemd (user) |
| OpenClaw Gateway | 18789 | 127.0.0.1 | ✅ Running | systemd (user) |
| OpenClaw Telegram | - | - | ❌ Disabled | - |

## Verified Integration Tests

- ✅ Ollama inference working (granite4.1:8b, ~133s first load on RTX 2060)
- ✅ OpenWebUI → Ollama via host.docker.internal
- ✅ Hermes Telegram connected (@lurkr_windows_bot)
- ✅ All ports bound to 127.0.0.1 only
- ✅ No Docker bridge exposure
- ✅ File permissions locked (600/700)

## Ollama Configuration (Critical)

- **Model storage**: `/var/lib/ollama/` (Linux filesystem, NOT /mnt/d/)
- **Service user**: `lurkr` (not `ollama`) - required for permission compatibility
- **Systemd override**: `/etc/systemd/system/ollama.service.d/override.conf`
- **GPU**: NVIDIA RTX 2060 6GB (CUDA 13.2)
- **Model**: granite4.1:8b (5GB, Q4_K_M)

## Security

- iptables DROP policy on INPUT
- All services localhost only
- Ollama Docker bridge disabled
- OpenClaw Telegram disabled (Hermes handles it)
- Docker: no-new-privileges, cap_drop ALL, read_only

## File Permissions

| Path | Perms |
|------|-------|
| `~/.hermes/.env` | 600 |
| `~/.hermes/config.yaml` | 600 |
| `~/.openclaw/openclaw.json` | 600 |
| `/srv/ai-stack/.env` | 600 |
| `~/.mempalace` | 700 |
