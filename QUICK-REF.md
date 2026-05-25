# Quick Reference - AI Agent Stack

## Emergency Recovery

### If everything is broken:
```bash
# 1. Kill all processes
pkill -f openclaw; pkill -f hermes; pkill -f "open-design"

# 2. Restart all services
systemctl --user restart hermes-gateway open-design openclaw-gateway
docker restart open-webui

# 3. Check status
~/hermes-health.sh
```

### If Telegram stops working:
```bash
# Check Hermes logs
journalctl --user -u hermes-gateway -n 50 | grep -i telegram

# Restart Hermes
systemctl --user restart hermes-gateway

# Check gateway state
cat ~/.hermes/gateway_state.json | python3 -m json.tool
```

### If OpenClaw crashes:
```bash
# Check logs
journalctl --user -u openclaw-gateway -n 50

# Restart
systemctl --user restart openclaw-gateway

# Verify
curl -sf http://127.0.0.1:18789/ && echo "OK" || echo "FAIL"
```

### If Docker breaks:
```bash
# Restart Docker
sudo systemctl restart docker

# Recreate OpenWebUI
cd /srv/ai-stack
docker compose down
docker compose up -d

# Check
docker ps
```

## Common Commands

### Service Management
```bash
# Status
systemctl --user status hermes-gateway open-design openclaw-gateway

# Restart all
systemctl --user restart hermes-gateway open-design openclaw-gateway

# Stop all
systemctl --user stop hermes-gateway open-design openclaw-gateway

# Logs
journalctl --user -u hermes-gateway -f
journalctl --user -u openclaw-gateway -f
journalctl --user -u open-design -f
```

### Port Reference
| Port | Service |
|------|---------|
| 11434 | Ollama |
| 8642 | Hermes API |
| 7457 | Open Design Daemon |
| 4000 | Open Design Web |
| 18789 | OpenClaw Gateway |
| 3000 | OpenWebUI |

### Quick Checks
```bash
# All ports listening
ss -tlnp | grep 127.0.0.1

# No external exposure
ss -tlnp | grep 0.0.0.0 && echo "EXPOSED!" || echo "Safe"

# File permissions
stat -c '%a %n' ~/.hermes/.env ~/.hermes/config.yaml ~/.openclaw/openclaw.json

# Docker health
docker ps --format '{{.Names}}: {{.Status}}'
```

## Backup & Restore

### Backup
```bash
~/hermes-backup.sh
```

### Restore from backup
```bash
BACKUP=/mnt/d/wslUbuntu/backups/hermes/BACKUP_FILE.tar.gz
tar xzf $BACKUP -C $HOME
```

## Configuration Files

| File | Purpose |
|------|---------|
| `~/.hermes/.env` | Hermes API keys |
| `~/.hermes/config.yaml` | Hermes config |
| `~/.openclaw/openclaw.json` | OpenClaw config |
| `/srv/ai-stack/.env` | Docker secrets |
| `/srv/ai-stack/docker-compose.yml` | OpenWebUI config |
| `~/.config/systemd/user/*.service` | Systemd units |

## Important Notes

1. **Telegram**: Only ONE service can use the bot token at a time
   - Hermes: enabled (default)
   - OpenClaw: disabled

2. **Ollama Bridge**: Must stay disabled
   ```bash
   sudo systemctl disable --now ollama-docker-bridge
   ```

3. **File Permissions**: Must be strict
   - `.env` files: 600
   - Config files: 600
   - Directories: 700

4. **Docker Images**: Always pin versions, never use `latest`

5. **All services bind to 127.0.0.1** - no exceptions
