#!/bin/bash
# Hermes Stack Health Check Script
# Usage: bash scripts/hermes-health.sh   (from repo root)
#        ~/hermes-health.sh              (from home symlink)
# Checks all services and reports status
#
# Uses $AI_PLATFORM_HOME (defaults to ~/ai-platform) or relative paths.

set -uo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'
FAILED=0

check() {
    local name="$1"
    local cmd="$2"

    if eval "$cmd" > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} ${name}"
    else
        echo -e "${RED}✗${NC} ${name} — DOWN"
        FAILED=1
    fi
}

check_http() {
    local name="$1"
    local url="$2"
    local expected="${3:-200}"

    local status
    status=$(curl -sf -o /dev/null -w '%{http_code}' --max-time 5 "$url" 2>/dev/null) || status="000"

    if [ "$status" = "$expected" ]; then
        echo -e "${GREEN}✓${NC} ${name} (HTTP ${status})"
    else
        echo -e "${RED}✗${NC} ${name} — HTTP ${status} (expected ${expected})"
        FAILED=1
    fi
}

echo "=== Hermes Stack Health Check [$(date '+%Y-%m-%d %H:%M:%S')] ==="
echo ""

echo "--- Core Services ---"
check "Ollama (127.0.0.1:11434)" "curl -sf --max-time 3 http://127.0.0.1:11434/"
check_http "Hermes Gateway" "http://127.0.0.1:8642/health"
check_http "OpenWebUI" "http://127.0.0.1:3000/" "200"
check_http "Open Design Web" "http://127.0.0.1:4000/" "200"
check_http "Open Design Daemon" "http://127.0.0.1:7457/api/health" "200"

echo ""
echo "--- Security Checks ---"
# Check for OpenClaw
if pgrep -f "openclaw" > /dev/null 2>&1; then
    echo -e "${RED}✗${NC} OpenClaw — RUNNING (should be disabled)"
    FAILED=1
else
    echo -e "${GREEN}✓${NC} OpenClaw — disabled"
fi

# Check for exposed ports (0.0.0.0 bindings that expose beyond localhost)
EXPOSED=$(ss -tlnp | awk '$4 !~ /^127\\./ && $4 !~ /::1/ && $4 ~ /:/' | grep -v '10\\.255\\.255\\.254' | wc -l)
if [ "$EXPOSED" -gt 0 ]; then
    echo -e "${RED}✗${NC} Network — ${EXPOSED} port(s) exposed beyond localhost:"
    ss -tlnp | awk '$4 !~ /^127\\./ && $4 !~ /::1/ && $4 ~ /:/' | grep -v '10\\.255\\.255\\.254' | while read line; do
        echo "    ${line}"
    done
    FAILED=1
fi

# Check iptables INPUT policy
POLICY=$(sudo iptables -L INPUT -n 2>/dev/null | head -1)
if echo "$POLICY" | grep -q "DROP"; then
    echo -e "${GREEN}✓${NC} Firewall — INPUT policy is DROP"
else
    echo -e "${YELLOW}⚠${NC} Firewall — INPUT policy is ACCEPT (permissive)"
fi

# Check file permissions
check "Hermes .env permissions (600)" "[ \"$(stat -c '%a' ~/.hermes/.env 2>/dev/null)\" = \"600\" ]"
check "MemPalace directory (700)" "[ \"$(stat -c '%a' ~/.mempalace 2>/dev/null)\" = \"700\" ]"

echo ""
echo "--- Docker ---"
if docker ps --format '{{.Status}}' | grep -q "unhealthy"; then
    echo -e "${RED}✗${NC} Docker — unhealthy containers detected"
    docker ps --format '{{.Names}}: {{.Status}}' | grep unhealthy
    FAILED=1
else
    echo -e "${GREEN}✓${NC} Docker — all containers healthy"
fi

# Check Docker log sizes
docker ps --format '{{.Names}}' | while read container; do
    LOG_SIZE=$(docker inspect "$container" --format='{{.LogPath}}' 2>/dev/null | xargs du -sh 2>/dev/null | cut -f1)
    if [ -n "$LOG_SIZE" ]; then
        echo "  ${container} logs: ${LOG_SIZE}"
    fi
done

echo ""
echo "--- MemPalace ---"
check "MemPalace MCP binary" "test -x $HOME/mempalace/.venv/bin/mempalace-mcp"
WING_COUNT=$(ls -d ~/.mempalace/wings/* 2>/dev/null | wc -l)
if [ "$WING_COUNT" -ge 4 ]; then
    echo -e "${GREEN}✓${NC} MemPalace wings — ${WING_COUNT} wings found"
else
    echo -e "${YELLOW}⚠${NC} MemPalace wings — only ${WING_COUNT} wings (expected 4+)"
fi

echo ""
echo "--- Disk Usage ---"
echo "  Root filesystem: $(df -h / | tail -1 | awk '{print $5 " used (" $4 " available)"}')"
echo "  MemPalace: $(du -sh ~/.mempalace 2>/dev/null | cut -f1)"
echo "  Ollama models: $(du -sh /mnt/d/wslUbuntu/ollama-models 2>/dev/null | cut -f1)"
echo "  OpenWebUI data: $(docker run --rm -v open-webui-data:/data alpine du -sh /data 2>/dev/null | cut -f1 || echo 'N/A')"

echo ""
echo "--- Backups ---"
BACKUP_DIR="/mnt/d/wslUbuntu/backups/hermes"
if [ -d "$BACKUP_DIR" ]; then
    BACKUP_COUNT=$(ls -1 "${BACKUP_DIR}"/*.tar.gz 2>/dev/null | wc -l)
    LATEST=$(ls -1t "${BACKUP_DIR}"/*.tar.gz 2>/dev/null | head -1)
    echo "  Backups available: ${BACKUP_COUNT}"
    if [ -n "$LATEST" ]; then
        echo "  Latest: $(basename "$LATEST") ($(du -sh "$LATEST" | cut -f1))"
    fi
else
    echo -e "${YELLOW}⚠${NC} No backup directory found at ${BACKUP_DIR}"
fi

echo ""
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}=== All checks passed ===${NC}"
    exit 0
else
    echo -e "${RED}=== Some checks failed ===${NC}"
    exit 1
fi