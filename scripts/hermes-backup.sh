#!/bin/bash
# Hermes Stack Backup Script
# Usage: ~/hermes-backup.sh
# Creates timestamped backups of all critical data

set -euo pipefail

BACKUP_BASE="/mnt/d/wslUbuntu/backups/hermes"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="${BACKUP_BASE}/${TIMESTAMP}"
RETENTION_DAYS=30

echo "=== Hermes Backup [${TIMESTAMP}] ==="

# Create backup directory
mkdir -p "${BACKUP_DIR}"

# 1. MemPalace data (wings, knowledge graph, chroma DB)
echo "[1/6] Backing up MemPalace..."
cp -a ~/.mempalace "${BACKUP_DIR}/mempalace"

# 2. Hermes config, sessions, skills, logs
echo "[2/6] Backing up Hermes..."
mkdir -p "${BACKUP_DIR}/hermes"
cp ~/.hermes/config.yaml "${BACKUP_DIR}/hermes/"
cp ~/.hermes/.env "${BACKUP_DIR}/hermes/"
cp -a ~/.hermes/sessions "${BACKUP_DIR}/hermes/" 2>/dev/null || true
cp -a ~/.hermes/skills "${BACKUP_DIR}/hermes/" 2>/dev/null || true
cp -a ~/.hermes/memories "${BACKUP_DIR}/hermes/" 2>/dev/null || true
cp -a ~/.hermes/logs "${BACKUP_DIR}/hermes/" 2>/dev/null || true
cp -a ~/.hermes/state.db* "${BACKUP_DIR}/hermes/" 2>/dev/null || true
cp -a ~/.hermes/response_store.db* "${BACKUP_DIR}/hermes/" 2>/dev/null || true
cp -a ~/.hermes/kanban.db "${BACKUP_DIR}/hermes/" 2>/dev/null || true

# 3. Open Design
echo "[3/6] Backing up Open Design..."
if [ -d ~/open-design ]; then
    cp -a ~/open-design/.env "${BACKUP_DIR}/" 2>/dev/null || true
    cp -a ~/open-design/.git "${BACKUP_DIR}/open-design-git" 2>/dev/null || true
fi

# 4. Ollama models (only metadata, not the actual models - they're large)
echo "[4/6] Backing up Ollama model list..."
ollama list > "${BACKUP_DIR}/ollama-models.txt" 2>/dev/null || echo "Ollama not running" > "${BACKUP_DIR}/ollama-models.txt"

# 5. OpenWebUI Docker volume
echo "[5/6] Backing up OpenWebUI data..."
docker run --rm \
    -v open-webui-data:/source:ro \
    -v "${BACKUP_DIR}:/backup" \
    alpine tar czf /backup/open-webui-data.tar.gz -C /source . 2>/dev/null || echo "OpenWebUI volume backup failed"

# 6. OpenClaw workspace (if exists)
echo "[6/6] Backing up OpenClaw workspace..."
if [ -d ~/.openclaw/workspace ]; then
    cp -a ~/.openclaw/workspace "${BACKUP_DIR}/openclaw-workspace" 2>/dev/null || true
fi

# Compress backup
echo "Compressing backup..."
cd "${BACKUP_BASE}"
tar czf "${TIMESTAMP}.tar.gz" "${TIMESTAMP}/"
rm -rf "${TIMESTAMP}/"

# Clean old backups
echo "Cleaning backups older than ${RETENTION_DAYS} days..."
find "${BACKUP_BASE}" -name "*.tar.gz" -mtime +${RETENTION_DAYS} -delete

echo ""
echo "=== Backup Complete ==="
echo "File: ${BACKUP_BASE}/${TIMESTAMP}.tar.gz"
echo "Size: $(du -sh "${BACKUP_BASE}/${TIMESTAMP}.tar.gz" | cut -f1)"
echo "Available backups: $(ls -1 "${BACKUP_BASE}"/*.tar.gz 2>/dev/null | wc -l)"
