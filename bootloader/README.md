# Hermes Forge

**Your personal AI agent stack. One command. Zero to running in 5 minutes.**

```bash
git clone https://github.com/joestechsolutions/hermes-forge.git ~/hermes-forge
cd ~/hermes-forge && bash bootstrap.sh run --snapshot my-deploy
```

Forge your own private AI infrastructure — Hermes Gateway, Dashboard, OpenClaw multi-agent orchestration, local LLMs with Ollama, and a ChatGPT-style UI with OpenWebUI. All locked down, all localhost-only, all yours.

---

## What You Get

| Service | Purpose | Port |
|---------|---------|------|
| **Hermes Gateway** | Your personal AI assistant — CLI + Telegram | 8642 |
| **Dashboard** | Live system monitor (web UI with real-time metrics) | 8643 |
| **OpenClaw** | Multi-agent orchestration team (24 sub-agents) | 18789 |
| **fcc Proxy** | Smart API routing to any provider | 8082 |
| **Ollama** | Local LLMs — no internet needed | 11434 |
| **OpenWebUI** | ChatGPT-style interface for local models | 3000 |

---

## Quick Start

### 1. Get a Server

Any Linux machine with **4GB RAM / 20GB storage**:
- Hostinger VPS ($12/mo)
- Hetzner CX22 ($5/mo)
- DigitalOcean Basic Droplet ($24/mo)
- Or your own machine

### 2. Get an API Key

Pick one provider:

| Provider | Cost | Sign Up |
|----------|------|---------|
| **OpenRouter** ⭐ | ~$0.50/mo light use | [openrouter.ai/keys](https://openrouter.ai/keys) |
| **NVIDIA NIM** | Free tier available | [build.nvidia.com](https://build.nvidia.com) |
| **DeepSeek** | $0.14/million tokens | [platform.deepseek.com](https://platform.deepseek.com) |
| **Ollama (local)** | Free | No key needed |

### 3. Deploy

```bash
ssh root@your-server-ip

# Clone and run
git clone https://github.com/joestechsolutions/ai-platform-bootloader.git ~/hermes-forge
cd ~/hermes-forge
bash bootstrap.sh run --snapshot initial-deploy
```

### 4. Configure

```bash
nano ~/hermes-forge/.env
# Paste your API key, save, exit

systemctl --user restart hermes-gateway
```

### 5. Verify

```bash
bash ~/hermes-forge/scripts/hermes-health.sh
# ✅ All 6 services running — or see which ones need attention
```

---

## Architecture

```
                         ┌──────────────────────┐
                         │  Telegram / CLI       │
                         └──────┬───────────────┘
                                │
                    ┌───────────▼───────────┐
                    │   Hermes Gateway      │
                    │   Port 8642           │
                    └───────┬──────┬────────┘
                            │      │
        ┌───────────────────┘      └────────────┐
        │                                       │
┌───────▼───────────┐               ┌───────────▼──────────┐
│  OpenClaw Agents  │               │  fcc Proxy (:8082)   │
│  Port 18789       │               │  Claude CLI Router   │
└───────────────────┘               └───────┬──────────────┘
                                            │
                    ┌───────────────────────┼──────────┐
                    │                       │          │
              ┌─────▼─────┐          ┌──────▼─────┐    │
              │ NVIDIA NIM │          │ OpenRouter │    │
              │  (Primary) │          │ (Fallback) │    │
              └───────────┘          └────────────┘    │
                                              ┌───────▼──────┐
                                              │  Ollama      │
                                              │  (Local)     │
                                              └──────────────┘
```

## Security

| Feature | Protection |
|---------|-----------|
| Services bind | 127.0.0.1 only — no external ports |
| Config files | 600 permissions — owner read/write only |
| Firewall | Default DROP policy on INPUT |
| Docker | Rootless, no-new-privileges, read-only fs |
| Telemetry | Disabled everywhere |
| API keys | In `.env` files, never in code |

## Cost Breakdown

| Tier | Monthly | Setup |
|------|---------|-------|
| **Free** — Local Ollama + free-tier APIs | $0 | Server only |
| **Light** — Chat, coding help, daily use | ~$0.50-2 | Server + OpenRouter |
| **Moderate** — Agent teams, automation | ~$5-10 | Server + NVIDIA/DeepSeek |
| **Heavy** — Full production | ~$15-30 | Server + premium providers |

## Troubleshooting

```bash
# Check service health
bash ~/hermes-forge/scripts/hermes-health.sh

# View logs
journalctl --user -u hermes-gateway -n 50 --no-pager

# Restart everything
systemctl --user restart hermes-gateway
systemctl --user restart openclaw-gateway
docker restart open-webui

# Fix permissions
chmod 600 ~/.hermes/.env ~/.hermes/config.yaml
```

---

## Roadmap

- [ ] Fresh VM CI/CD pipeline — automatic smoke test on new VPS
- [ ] One-liner curl install (no git clone needed)
- [ ] Web-based setup wizard for non-technical users
- [ ] Managed hosting option (deploy + manage for clients)
- [ ] Plugin marketplace

## Support

- Open a [GitHub Issue](https://github.com/joestechsolutions/hermes-forge/issues)
- Contact: [joe@joestechsolutions.com](mailto:joe@joestechsolutions.com)

---

*Built by [Joe's Tech Solutions](https://github.com/joestechsolutions/hermes-forge) — Forge your own AI infrastructure.*