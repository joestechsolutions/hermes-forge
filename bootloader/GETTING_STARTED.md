# Hermes AI Platform — One-Shot Deployment Guide

**Your personal AI agent stack. One command to deploy. Bring your own API key.**

---

## What You Get

A complete, production-ready AI agent infrastructure running on a single machine:

```
Hermes Gateway (:8642)    — Your personal AI assistant (Telegram + CLI)
├── Dashboard (:8643)     — Live system monitor (web UI)
├── OpenClaw (:18789)     — Multi-agent orchestration team
├── fcc Proxy (:8082)     — Smart API routing to your chosen provider
├── Ollama (:11434)       — Local LLMs (no internet needed for basic tasks)
└── OpenWebUI (:3000)     — ChatGPT-style interface for local models
```

**One command to deploy the entire stack.** No manual setup of each service.

---

## Prerequisites

### 1. A Server or VM

Any Linux machine with **4GB RAM minimum (8GB recommended)** and **20GB storage**:

| Provider | Recommended Plan | Cost |
|----------|-----------------|------|
| Hostinger | VPS KVM 2 (4GB RAM, 80GB SSD) | ~$12-15/month |
| Hetzner | CX22 (4GB RAM, 40GB SSD) | ~$5-8/month |
| DigitalOcean | Basic Droplet (4GB RAM, 80GB SSD) | ~$24/month |
| Any Ubuntu 24.04 VM | Your own hardware | Free |

**Supported OS:** Ubuntu 24.04 LTS (recommended), Debian 12, or any modern Linux distribution.

### 2. An API Key (Choose One)

You need at least one AI provider key. Pick the one that works for you:

| Provider | Cost | Sign Up |
|----------|------|---------|
| **OpenRouter** (recommended) | Pay-as-you-go, ~$0.50/month for light use | [openrouter.ai/keys](https://openrouter.ai/keys) |
| **NVIDIA NIM** | Free tier available, $0 for many models | [build.nvidia.com](https://build.nvidia.com) |
| **DeepSeek** | Very cheap ($0.14/million tokens) | [platform.deepseek.com](https://platform.deepseek.com) |

**Tip:** OpenRouter is the easiest — one key gives you access to 200+ models including free-tier options.

### 3. A Telegram Bot Token (Optional)

If you want your AI assistant on Telegram:
1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot` and follow the prompts
3. Save the token it gives you

---

## Quick Start (5 Minutes)

### Step 1: Connect to Your Server

```bash
ssh root@your-server-ip
```

### Step 2: Clone and Run the Bootloader

```bash
# Clone the platform repo
git clone https://github.com/joestechsolutions/hermes-forge.git ~/hermes-forge

# Run the bootstrapper
cd ~/hermes-forge/bootloader
bash bootstrap.sh run --snapshot initial-deploy
```

This single command installs everything:
- Python 3.12, Node.js 22, Docker
- All services (Hermes, Dashboard, OpenClaw, Ollama, OpenWebUI)
- Firewall rules (locked down to localhost only)
- Systemd services (auto-start on boot)

**What the bootloader does:**
1. Installs system dependencies (Python, Node.js, Docker)
2. Sets up all config files from templates
3. Creates systemd services for each component
4. Takes a snapshot before any changes (so you can roll back)
5. Verifies everything is running correctly

### Step 3: Configure Your API Key

```bash
nano ~/hermes-forge/.env
```

Find your provider section and paste your API key:

```bash
# Choose ONE provider and uncomment it:

# For OpenRouter (recommended):
PROVIDER_TYPE=openrouter
OPENROUTER_API_KEY=sk-or-v1-your-key-here

# For NVIDIA NIM:
# PROVIDER_TYPE=nvidia_nim
# NVIDIA_NIM_API_KEY=nvapi-your-key-here

# For DeepSeek:
# PROVIDER_TYPE=deepseek
# DEEPSEEK_API_KEY=sk-your-key-here
```

### Step 4: (Optional) Add Telegram

```bash
nano ~/hermes-forge/.env
# Add:
TELEGRAM_BOT_TOKEN=your-bot-token-from-botfather
```

### Step 5: Restart and Verify

```bash
systemctl --user restart hermes-gateway
bash ~/hermes-forge/scripts/hermes-health.sh
```

**Post-install verification:** The health check confirms all services respond correctly, ports are locked down to localhost, and permissions are secure.

You should see:
```
✅ Hermes Gateway — active on :8642
✅ Dashboard — active on :8643
✅ OpenClaw — active on :18789
✅ Ollama — active on :11434
✅ OpenWebUI — active on :3000
✅ fcc Proxy — active on :8082
```

---

## What to Do Next

### Talk to Your AI on Telegram
Send `/start` to your bot. It's powered by the same model you configured.

### Check the Dashboard
Open `http://your-server-ip:8643` in a browser.
- See real-time service status
- View system metrics (CPU, RAM, disk)
- Restart services with one click

### Use OpenWebUI
Open `http://your-server-ip:3000` for a ChatGPT-style interface to local models.

---

## Architecture Overview

```
                         ┌─────────────────────────┐
                         │     Telegram / CLI       │
                         │     (Your Interface)     │
                         └──────────┬──────────────┘
                                    │
                         ┌──────────▼──────────────┐
                         │    Hermes Gateway        │
                         │    (Orchestrator)        │
                         │    Port 8642             │
                         └──────┬──────┬───────────┘
                                │      │
           ┌────────────────────┘      └──────────────┐
           │                                          │
┌──────────▼──────────┐              ┌────────────────▼──────────┐
│   OpenClaw Agents   │              │     fcc Proxy (:8082)     │
│   (Multi-Agent Team)│              │     Claude CLI Router     │
│   Port 18789        │              │                           │
└─────────────────────┘              └──────┬────────────────────┘
                                            │
                          ┌─────────────────┼──────────────────┐
                          │                 │                  │
                    ┌─────▼─────┐    ┌──────▼──────┐   ┌──────▼──────┐
                    │ NVIDIA NIM│    │  OpenRouter  │   │   Ollama    │
                    │ (Primary) │    │  (Fallback)  │   │  (Local)    │
                    └───────────┘    └─────────────┘   └─────────────┘
```

## Security

This system is built with zero-trust principles:

| Feature | How It's Protected |
|---------|-------------------|
| All services | Listen on 127.0.0.1 only — no external exposure |
| Config files | Permission 600 (owner read/write only) |
| API keys | Stored in `.env` files, never in code |
| Firewall | Default DROP policy on INPUT |
| Docker | No new privileges, read-only filesystem, all capabilities dropped |
| Telemetry | Disabled everywhere |
| Data | Never leaves your machine when using local models |

## Troubleshooting

### "Service won't start"

```bash
# Check what went wrong
journalctl --user -u hermes-gateway -n 50 --no-pager

# Common fix: wrong API key
nano ~/hermes-forge/.env
# Verify your API key is correct
systemctl --user restart hermes-gateway
```

### "Can't connect to Telegram"

```bash
# Check if bot token is set
grep TELEGRAM_BOT_TOKEN ~/hermes-forge/.env

# Bot token should be from @BotFather
# Format: 1234567890:ABCdefGHIjklmNOPqrstUVwxyz
```

### "Need to restart everything"

```bash
bash ~/hermes-forge/scripts/hermes-health.sh    # See what's running
systemctl --user restart hermes-gateway
systemctl --user restart openclaw-gateway
docker restart open-webui
```

## Cost Estimates

| Usage Level | Monthly Cost | Provider |
|------------|-------------|----------|
| Light (chat, coding help) | ~$0.50-2 | OpenRouter (free tier models) |
| Moderate (daily use, agents) | ~$5-10 | OpenRouter (paid models) |
| Heavy (full agent teams) | ~$15-30 | NVIDIA NIM / DeepSeek |
| Local only (no API key) | $0 | Ollama (granite, llama) |

---

## Support

- **Issues:** Open a GitHub issue at [github.com/your-org/hermes-bootloader](https://github.com/your-org/hermes-bootloader)
- **Questions:** Join our Discord (link coming soon)
- **Custom deployments:** Contact [joe@joestechsolutions.com](mailto:joe@joestechsolutions.com)

---

*Built with Hermes AI Platform v0.14.0 — Your personal AI infrastructure.*