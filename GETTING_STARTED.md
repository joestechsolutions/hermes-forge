# Hermes AI Platform — One-Shot Deployment Guide

**Your personal AI agent stack. One command to deploy. Bring your own API key.**

**Linux or macOS — one command deploys the same stack on both.**

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

**Supported OS:** Ubuntu 24.04 LTS (recommended), Debian 12, modern Linux distributions, **or macOS 13+ (Ventura)**.

### macOS Prerequisites

If deploying on macOS, ensure the following are installed first:

| Requirement | Notes |
|-------------|-------|
| **macOS 13+ (Ventura or newer)** | Apple Silicon (M1/M2/M3/M4) or Intel |
| **Xcode Command Line Tools** | Auto-prompted by `bootstrap.sh`, or run `xcode-select --install` |
| **Homebrew** | Auto-installed by `bootstrap.sh` if missing. Required for Node.js and service management. |
| **Docker Desktop** | [Download from docker.com](https://www.docker.com/products/docker-desktop/) — the curl install script at `get.docker.com` also works |
| **Disk space** | 20GB+ free (models can add 10-30GB) |

> **Note:** The bootstrap.sh script detects your platform automatically and adapts install paths, service managers, and dependency commands. Same single command works on both Linux and macOS.

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

### Step 1: Open a Terminal on Your Machine

**On a Linux server:**
```bash
ssh root@your-server-ip
```

**On macOS (local deployment):**
Just open Terminal — you're already there. The bootloader runs natively.

> The same `bootstrap.sh` command works on both platforms. Platform detection is automatic.

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
- Auto-start services via systemd (Linux) or launchd / Homebrew services (macOS)

**What the bootloader does:**
1. Installs system dependencies (Python, Node.js, Docker)
2. Sets up all config files from templates
3. Creates systemd services (Linux) or LaunchAgent plists (macOS) for each component
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
# Linux (systemd):
systemctl --user restart hermes-gateway

# macOS (launchd):
brew services restart hermes-gateway

# Check everything is running (works on both platforms):
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

**Linux:**
```bash
# Check what went wrong
journalctl --user -u hermes-gateway -n 50 --no-pager

# Common fix: wrong API key
nano ~/hermes-forge/.env
systemctl --user restart hermes-gateway
```

**macOS:**
```bash
# Check what went wrong (console log)
log show --predicate 'process == "hermes-gateway"' --last 10m

# Or check Homebrew service status
brew services list

# Common fix: wrong API key
nano ~/hermes-forge/.env
brew services restart hermes-gateway
```

### "Can't connect to Telegram"

```bash
# Check if bot token is set
grep TELEGRAM_BOT_TOKEN ~/hermes-forge/.env

# Bot token should be from @BotFather
# Format: 1234567890:ABCdefGHIjklmNOPqrstUVwxyz
```

### "Need to restart everything"

**Linux:**
```bash
bash ~/hermes-forge/scripts/hermes-health.sh    # See what's running
systemctl --user restart hermes-gateway
systemctl --user restart openclaw-gateway
docker restart open-webui
```

**macOS:**
```bash
bash ~/hermes-forge/scripts/hermes-health.sh    # See what's running
brew services restart hermes-gateway
brew services restart openclaw-gateway
docker restart open-webui
```

---

## macOS Support

The Hermes AI Platform runs natively on macOS 13+ (Ventura) alongside Linux. The same `bootstrap.sh` command automatically detects your platform and adapts everything — from package managers to service management to file paths.

### Key Differences from Linux

| Aspect | Linux (Ubuntu/Debian) | macOS |
|--------|----------------------|-------|
| Package manager | `apt` | `brew` (Homebrew) |
| Service manager | `systemctl --user` / systemd units | `brew services` / `launchctl` / LaunchAgent plists |
| Firewall | `iptables` / `ufw` | `pfctl` / System Settings |
| Docker | Docker Engine (via `apt`) | Docker Desktop (from docker.com) |
| Install prefix | `/srv/ai-stack` | `/usr/local/var/ai-stack` (no `sudo` needed) |
| Service files | `/etc/systemd/user/` | `~/Library/LaunchAgents/` |
| Logs | `journalctl --user -u <service>` | `log show --predicate 'process == "<service>"'` |
| User/group mgmt | `usermod -aG docker $USER` | Not needed — Docker Desktop handles this |
| Node.js install | NodeSource apt repo | `brew install node@22` |

### Platform Detection

The bootloader handles everything automatically:

```
bootstrap.sh
├── Detects OS via `uname -s`
├── Linux → apt, systemd, iptables, /srv/ai-stack
└── macOS → brew, launchd, pfctl, /usr/local/var/ai-stack
```

Same one-liner, different internals. You don't need to choose a platform — just run `bash bootstrap.sh run`.

### Command Equivalents

| You want to... | Linux command | macOS command |
|---------------|--------------|---------------|
| Restart a service | `systemctl --user restart <name>` | `brew services restart <name>` |
| View service logs | `journalctl --user -u <name> -n 50` | `log show --predicate 'process=="<name>"' --last 10m` |
| List running services | `systemctl --user list-units` | `brew services list` |
| Stop a service | `systemctl --user stop <name>` | `brew services stop <name>` |
| Start on boot | `systemctl --user enable <name>` | Handled by LaunchAgent plist in `~/Library/LaunchAgents/` |
| Check firewall rules | `sudo iptables -L` | `sudo pfctl -sr` |
| Edit environment | `nano ~/hermes-forge/.env` | `nano ~/hermes-forge/.env` (same) |
| Run health check | `bash ~/hermes-forge/scripts/hermes-health.sh` | `bash ~/hermes-forge/scripts/hermes-health.sh` (same) |

### Path Differences

On macOS, all files live under `/usr/local/var/ai-stack` instead of `/srv/ai-stack`. This avoids requiring `sudo` for installation and is consistent with Homebrew conventions. The bootloader handles this mapping:

| Component | Linux path | macOS path |
|-----------|-----------|------------|
| Config root | `/srv/ai-stack/config` | `/usr/local/var/ai-stack/config` |
| Data directory | `/srv/ai-stack/data` | `/usr/local/var/ai-stack/data` |
| Logs | `/srv/ai-stack/logs` | `/usr/local/var/ai-stack/logs` |
| LaunchAgent | N/A | `~/Library/LaunchAgents/io.hermes.*.plist` |

### macOS Troubleshooting Tips

#### Homebrew permissions

```bash
# If you get permission errors, Homebrew may need ownership fixed:
sudo chown -R $(whoami) /usr/local/var/ai-stack

# Or reinstall Homebrew if brew itself is broken:
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

#### SIP (System Integrity Protection)

SIP does not interfere with the AI stack. The bootloader installs everything under `/usr/local/var/` and `~/Library/LaunchAgents/`, which are both outside SIP-protected paths. If you're using a custom path under `/System/` or `/usr/bin/`, you may need to adjust.

#### Docker Desktop conflicts

- If Docker Desktop is already running, the bootloader skips Docker installation
- Ensure Docker Desktop has sufficient resources: at least 4GB RAM and 4 CPUs in Docker Desktop → Settings → Resources
- The bootloader does **not** manage the Docker group on macOS — Docker Desktop handles permissions via the `docker` socket already

#### Firewall (pfctl) notes

macOS uses `pfctl` (Packet Filter) instead of `iptables`. The bootloader configures it to lock services to localhost:

```bash
# View active pf rules
sudo pfctl -sr

# Reload pf configuration after bootloader changes
sudo pfctl -f /etc/pf.conf

# pfctl resets on reboot — the bootloader's LaunchAgent re-applies rules at login
```

#### "brew command not found"

If Homebrew isn't installed, the bootloader installs it automatically. To install manually:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

#### Apple Silicon (M1/M2/M3/M4) notes

- All tools (Python, Node.js, Docker Desktop) are natively supported on ARM64
- No Rosetta 2 required, though Docker Desktop may prompt to install it for x86 containers
- Ollama runs natively on Apple Silicon with GPU acceleration via Metal

---

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