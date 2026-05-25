# AI Platform

Multi-agent AI architecture with Hermes, OpenClaw, Open Design, and OpenWebUI.

## Quick Start

### Recovery from scratch:
```bash
bash scripts/bootloader.sh
```

### Current state:
```bash
cat STATE.md
```

### Health check:
```bash
bash scripts/hermes-health.sh
```

**Post-install verification:** Run the health check script to confirm all services are up, ports are locked down, and file permissions are correct. A clean output means your stack is ready to use.

### Backup:
```bash
bash scripts/hermes-backup.sh
```

## Structure
```
ai-platform/
├── README.md              # This file
├── STATE.md               # Current state snapshot
├── QUICK-REF.md           # Emergency recovery commands
├── blueprints/
│   └── ARCHITECTURE.md    # Full architecture docs
├── configs/
│   ├── hermes-gateway.service
│   ├── open-design.service
│   ├── openclaw-gateway.service
│   ├── ollama-override.conf  # Ollama systemd override (CRITICAL)
│   └── docker-compose.yml
└── scripts/
    ├── bootloader.sh      # Full automated setup
    ├── hermes-backup.sh
    └── hermes-health.sh
```

## Components
- **Hermes** - Messaging gateway (Telegram) + terminal agent
- **OpenClaw** - Multi-agent system (30+ agents)
- **Open Design** - Design AI stack
- **OpenWebUI** - Web UI for local LLMs (Docker)
- **Ollama** - Local model inference (RTX 2060 GPU)

## Critical Rules
1. All services bind to 127.0.0.1 only
2. Telegram handled by Hermes only (OpenClaw Telegram disabled)
3. Ollama Docker bridge disabled
4. File permissions: 600 for secrets, 700 for sensitive dirs
5. Pinned Docker images (no latest tags)
6. **Ollama models MUST be on Linux filesystem** (`/var/lib/ollama/`), NOT `/mnt/d/` (too slow, causes timeouts)

## Ollama Setup (After Bootloader)
```bash
# 1. Apply systemd override
sudo cp configs/ollama-override.conf /etc/systemd/system/ollama.service.d/override.conf
sudo sed -i "s/User=lurkr/User=${USER}/" /etc/systemd/system/ollama.service.d/override.conf
sudo sed -i "s/Group=lurkr/Group=${USER}/" /etc/systemd/system/ollama.service.d/override.conf

# 2. Create model storage
sudo mkdir -p /var/lib/ollama
sudo chown ${USER}:${USER} /var/lib/ollama

# 3. Pull models
ollama pull granite4.1:8b

# 4. Restart
sudo systemctl daemon-reload && sudo systemctl restart ollama
```
