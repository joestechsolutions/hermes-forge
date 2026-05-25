# AI Platform Architecture - Infrastructure State

**Last Updated:** 2026-05-05
**Machine:** joBlade (WSL2 Ubuntu)
**Blueprint Location:** ~/ai-platform/

## Active Services (ALL verified working)

| Service | Port | Bind | Method | Status |
|---------|------|------|--------|--------|
| Ollama | 11434 | 127.0.0.1 | systemd (system) | ✅ Running |
| Hermes Gateway | 8642 | 127.0.0.1 | systemd (user) | ✅ Running |
| - Telegram | - | - | - | ✅ Connected (@lurkr_windows_bot) |
| - API Server | - | - | - | ✅ Connected |
| Open Design Web | 4000 | 127.0.0.1 | systemd (user) | ✅ Running |
| Open Design Daemon | 7457 | 127.0.0.1 | systemd (user) | ✅ Running |
| OpenClaw Gateway | 18789 | 127.0.0.1 | systemd (user) | ✅ Running |
| OpenWebUI | 3000 | 127.0.0.1 | Docker | ✅ Healthy |

## Service Commands

```bash
# Check all services
systemctl --user status hermes-gateway open-design openclaw-gateway
docker ps
sudo systemctl status ollama

# Restart all
systemctl --user restart hermes-gateway open-design openclaw-gateway
docker restart open-webui
sudo systemctl restart ollama

# View logs
journalctl --user -u hermes-gateway -f
journalctl --user -u openclaw-gateway -f
journalctl --user -u open-design -f
sudo journalctl -u ollama -f
```

## Ollama Configuration (CRITICAL)

- **Model path:** `/var/lib/ollama/` (Linux filesystem)
- **NOT on /mnt/d/** - Windows NTFS is too slow, causes 2min+ load timeouts
- **Service user:** lurkr (not ollama)
- **Override:** `/etc/systemd/system/ollama.service.d/override.conf`
- **GPU:** NVIDIA RTX 2060 6GB (CUDA 13.2)
- **Model:** granite4.1:8b (5GB, Q4_K_M)
- **Load time:** ~133s first load, then stays in memory for 5min

## Integration Map

- **Hermes** handles Telegram exclusively (OpenClaw Telegram disabled)
- **OpenWebUI** connects to Ollama via `host.docker.internal:11434`
- **OpenClaw** uses Ollama for local model inference
- **All services** bind to 127.0.0.1 only (no external exposure)
- **MCP:** MemPalace at `~/.mempalace` (mempalace-mcp binary)

## Security

- **iptables:** DROP policy on INPUT (blocks non-localhost)
- **Ollama bridge:** DISABLED (no Docker container access)
- **OpenClaw Telegram:** DISABLED in openclaw.json
- **File permissions:** 600 for .env/config, 700 for dirs
- **Docker:** no-new-privileges, cap_drop ALL, read_only

## Recovery

- **Blueprint:** `~/ai-platform/` (bootloader.sh + configs)
- **Backup script:** `~/ai-platform/scripts/hermes-backup.sh`
- **Health check:** `~/ai-platform/scripts/hermes-health.sh`
- **D: drive backup:** `/mnt/d/wslUbuntu/ai-platform-backup/`

## Model Providers

| Provider | Role | Models |
|----------|------|--------|
| NVIDIA NIM | Primary | stepfun-ai/step-3.5-flash, minimax-m2.7 |
| OpenRouter | Fallback | qwen/qwen3-coder:free, nemotron variants |
| Ollama | Local | granite4.1:8b |
| OpenClaw | Agents | Claude (Anthropic), Gemini, OpenRouter |

## Telegram

- **Bot:** @lurkr_windows_bot (ID: 8711286854)
- **Token:** in ~/.hermes/.env (TELEGRAM_BOT_TOKEN)
- **Handler:** Hermes Gateway (NOT OpenClaw)
- **Allowed users:** 6878695078 (configured in config.yaml)
