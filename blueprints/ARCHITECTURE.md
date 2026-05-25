# AI Agent Stack - Architecture Blueprint

**Version:** 1.0.0
**Created:** 2026-05-05
**Host:** joBlade (WSL2 Ubuntu)

## Overview

Multi-agent AI architecture with three frameworks running simultaneously:
- **Hermes** - Messaging gateway (Telegram) + terminal agent
- **OpenClaw** - Multi-agent system with 30+ specialized agents
- **Open Design** - Design AI stack with web interface
- **OpenWebUI** - Docker-hosted web UI for local LLMs
- **Ollama** - Local model inference server

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                      User Access                         │
├────────────┬─────────────┬──────────────┬───────────────┤
│  Telegram  │ OpenWebUI   │ Open Design  │ OpenClaw Web  │
│  (mobile)  │ (browser)   │  Web (4000)  │  Gateway UI   │
│            │  (3000)     │              │   (18789)     │
└─────┬──────┴──────┬──────┴──────┬───────┴───────┬───────┘
      │             │             │               │
┌─────▼──────┐ ┌────▼──────┐ ┌───▼────────┐ ┌───▼────────┐
│   Hermes   │ │ OpenWebUI │ │ Open Design│ │  OpenClaw  │
│  Gateway   │ │ (Docker)  │ │ Daemon     │ │  Gateway   │
│  (8642)    │ │           │ │ (7457)     │ │            │
└─────┬──────┘ └────┬──────┘ └────┬───────┘ └───┬────────┘
      │             │             │             │
      └─────────────┴─────────────┴─────────────┘
                      │
              ┌───────▼───────┐
              │    Ollama     │
              │   (11434)     │
              │  Local LLMs   │
              └───────────────┘
```

## Service Matrix

| Service | Port | Bind | Method | Restart | Status |
|---------|------|------|--------|---------|--------|
| Ollama | 11434 | 127.0.0.1 | systemd (system) | always | ✅ |
| Hermes Gateway | 8642 | 127.0.0.1 | systemd (user) | always | ✅ |
| Open Design Web | 4000 | 127.0.0.1 | systemd (user) | on-failure | ✅ |
| Open Design Daemon | 7457 | 127.0.0.1 | systemd (user) | on-failure | ✅ |
| OpenClaw Gateway | 18789 | 127.0.0.1 | systemd (user) | on-failure | ✅ |
| OpenWebUI | 3000 | 127.0.0.1 | Docker | unless-stopped | ✅ |

## Critical Rules

1. **ALL services bind to 127.0.0.1 only** - no 0.0.0.0 exposure
2. **Telegram handled by Hermes only** - OpenClaw Telegram disabled
3. **Ollama bridge disabled** - no Docker container access to Ollama
4. **File permissions locked** - 600 for secrets, 700 for sensitive dirs
5. **Pinned Docker images** - no `latest` tags
6. **Telemetry disabled** - all analytics turned off

## Directory Structure

```
/home/lurkr/
├── .hermes/                          # Hermes Agent (700)
│   ├── .env                          # API keys (600)
│   ├── config.yaml                   # Main config (600)
│   ├── hermes-agent/                 # Source code + venv
│   ├── node/bin/                     # node, npm, pnpm, openclaw
│   ├── skills/                       # 27 skill categories
│   ├── logs/                         # Runtime logs (700)
│   ├── sessions/                     # Session data (700)
│   ├── state.db                      # SQLite database
│   └── gateway_state.json            # Platform states
├── .openclaw/                        # OpenClaw (700)
│   ├── openclaw.json                # Config (600)
│   ├── workspace/                    # Agent workspaces
│   └── agents/                       # 30+ agent definitions
├── .config/systemd/user/             # User services
│   ├── hermes-gateway.service
│   ├── open-design.service
│   ├── openclaw-gateway.service
│   └── default.target.wants/         # Enabled symlinks
├── open-design/                      # Open Design project
├── mempalace/                        # MemPalace MCP server
├── .mempalace/                       # MemPalace data (700)
├── hermes-backup.sh                  # Weekly backup script
├── hermes-health.sh                  # Health check script
└── STATE.md                          # Current state document

/srv/ai-stack/
├── docker-compose.yml                # OpenWebUI config
└── .env                              # Docker secrets (600)
```

## Dependencies

| Component | Version | Notes |
|-----------|---------|-------|
| Node.js | v22.x | Required for OpenClaw, Open Design |
| Python | 3.12 | Required for Hermes, MemPalace |
| pnpm | 10.x | Node package manager |
| Docker | 29.x | Container runtime |
| Ollama | 0.23+ | Local LLM inference |
| systemd | 250+ | Service management |

## Configuration Files

### Hermes (.env) - Template
```env
# Core API Keys
TELEGRAM_BOT_TOKEN=<from @BotFather>
NVIDIA_API_KEY=nvapi-<from NVIDIA NIM>
FAL_KEY=<from fal.ai>
FIRECRAWL_API_KEY=<from firecrawl>
OPENROUTER_API_KEY=sk-or-v1-<from openrouter>

# Hermes API Server
API_SERVER_ENABLED=true
API_SERVER_KEY=<generate 64 char hex>
API_SERVER_PORT=8642
API_SERVER_HOST=127.0.0.1

# Telegram
HERMES_TELEGRAM_FALLBACK_IPS=149.154.166.110,149.154.167.220,149.154.166.138,149.154.167.230
```

### Docker Compose (.env) - Template
```env
WEBUI_SECRET_KEY=<generate 64 char hex>
```

## Telegram Conflict Resolution

Both Hermes and OpenClaw support Telegram, but only one can use a bot token at a time.

**Current Setup:**
- Hermes: `channels.telegram.enabled = true` (via config.yaml)
- OpenClaw: `channels.telegram.enabled = false` (via openclaw.json)

If you need OpenClaw Telegram, disable Hermes Telegram and vice versa.

## Security Checklist

- [ ] All services bind to 127.0.0.1
- [ ] File permissions: 600 for .env/config, 700 for dirs
- [ ] Docker: no-new-privileges, cap_drop ALL, read_only
- [ ] No `latest` tags in Docker images
- [ ] Telemetry disabled in all services
- [ ] Ollama bridge disabled
- [ ] OpenClaw Telegram disabled (if Hermes uses it)
- [ ] iptables firewall configured
- [ ] Backups scheduled and verified

## Recovery Commands

```bash
# Check all services
systemctl --user status hermes-gateway open-design openclaw-gateway
docker ps

# Restart all
systemctl --user restart hermes-gateway open-design openclaw-gateway
docker restart open-webui

# View logs
journalctl --user -u hermes-gateway -f --since "1 hour ago"
journalctl --user -u openclaw-gateway -f --since "1 hour ago"

# Health check
~/hermes-health.sh

# Backup
~/hermes-backup.sh
```
