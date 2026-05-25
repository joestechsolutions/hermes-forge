#!/usr/bin/env bash
set -euo pipefail

# AI Agent Stack Bootloader
# Version: 1.0.0
# Date: 2026-05-05
# Description: Sets up the complete multi-agent AI architecture
# Usage: curl -fsSL <url> | bash  OR  bash bootloader.sh

# ============================================================================
# CONFIGURATION
# ============================================================================

USER_HOME="${HOME}"
AI_STACK_DIR="/srv/ai-stack"
SYSTEMD_DIR="${USER_HOME}/.config/systemd/user"
HERMES_HOME="${USER_HOME}/.hermes"
OPENCLAW_HOME="${USER_HOME}/.openclaw"
MEMPALACE_HOME="${USER_HOME}/.mempalace"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

check_root() {
    if [[ $EUID -eq 0 ]]; then
        log_error "This script should NOT be run as root. Use a regular user with sudo access."
        exit 1
    fi
}

check_wsl() {
    if grep -qi microsoft /proc/version 2>/dev/null; then
        IS_WSL=true
        log_info "WSL2 detected"
    else
        IS_WSL=false
        log_info "Native Linux detected"
    fi
}

command_exists() { command -v "$1" &>/dev/null; }

generate_secret() {
    openssl rand -hex 32
}

backup_existing() {
    local dir="$1"
    if [[ -d "$dir" ]]; then
        local backup="${dir}.backup-$(date +%Y%m%d-%H%M%S)"
        log_warn "Backing up existing ${dir} to ${backup}"
        cp -r "$dir" "$backup"
    fi
}

# ============================================================================
# SYSTEM DEPENDENCIES
# ============================================================================

install_system_deps() {
    log_info "Installing system dependencies..."

    sudo apt-get update
    sudo apt-get install -y \
        curl \
        wget \
        git \
        python3 \
        python3-venv \
        python3-pip \
        build-essential \
        iptables \
        jq \
        openssl \
        socat \
        unzip

    log_success "System dependencies installed"
}

install_nodejs() {
    if command_exists node; then
        log_info "Node.js already installed: $(node --version)"
        return
    fi

    log_info "Installing Node.js 22.x..."

    # Install via NodeSource
    curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
    sudo apt-get install -y nodejs

    # Verify
    log_success "Node.js installed: $(node --version)"
}

install_pnpm() {
    if command_exists pnpm; then
        log_info "pnpm already installed: $(pnpm --version)"
        return
    fi

    log_info "Installing pnpm..."
    npm install -g pnpm
    log_success "pnpm installed: $(pnpm --version)"
}

install_docker() {
    if command_exists docker; then
        log_info "Docker already installed: $(docker --version)"
        return
    fi

    log_info "Installing Docker..."

    # Official Docker install
    curl -fsSL https://get.docker.com | sudo sh

    # Add user to docker group
    sudo usermod -aG docker "$USER"

    # Start Docker
    sudo systemctl enable docker
    sudo systemctl start docker

    log_success "Docker installed: $(docker --version)"
    log_warn "You may need to log out and back in for docker group changes to take effect"
}

install_ollama() {
    if command_exists ollama; then
        log_info "Ollama already installed: $(ollama --version)"
        return
    fi

    log_info "Installing Ollama..."

    curl -fsSL https://ollama.com/install.sh | sudo sh

    # Stop Ollama
    sudo systemctl stop ollama 2>/dev/null || true

    # Create model storage on Linux filesystem (NOT /mnt/d/ - too slow)
    sudo mkdir -p /var/lib/ollama
    sudo chown "${USER}:${USER}" /var/lib/ollama

    # Configure Ollama override
    sudo mkdir -p /etc/systemd/system/ollama.service.d
    cat <<'EOF' | sudo tee /etc/systemd/system/ollama.service.d/override.conf
[Service]
Environment=
Environment="OLLAMA_HOST=127.0.0.1:11434"
Environment="OLLAMA_MODELS=/var/lib/ollama"
Environment="OLLAMA_NO_CLOUD=true"
User=lurkr
Group=lurkr
EOF

    # Fix User/Group to current user
    sudo sed -i "s/User=lurkr/User=${USER}/" /etc/systemd/system/ollama.service.d/override.conf
    sudo sed -i "s/Group=lurkr/Group=${USER}/" /etc/systemd/system/ollama.service.d/override.conf

    sudo systemctl daemon-reload
    sudo systemctl enable ollama
    sudo systemctl start ollama

    log_success "Ollama installed and configured"
    log_warn "Pull models: ollama pull granite4.1:8b (first load ~133s on RTX 2060)"
}

# ============================================================================
# DIRECTORY STRUCTURE
# ============================================================================

create_directories() {
    log_info "Creating directory structure..."

    mkdir -p "${HERMES_HOME}"
    mkdir -p "${HERMES_HOME}/logs"
    mkdir -p "${HERMES_HOME}/sessions"
    mkdir -p "${HERMES_HOME}/memories"
    mkdir -p "${HERMES_HOME}/checkpoints"
    mkdir -p "${OPENCLAW_HOME}"
    mkdir -p "${OPENCLAW_HOME}/workspace"
    mkdir -p "${MEMPALACE_HOME}"
    mkdir -p "${AI_STACK_DIR}"
    mkdir -p "${SYSTEMD_DIR}"

    # Set permissions
    chmod 700 "${HERMES_HOME}"
    chmod 700 "${OPENCLAW_HOME}"
    chmod 700 "${MEMPALACE_HOME}"

    log_success "Directory structure created"
}

# ============================================================================
# HERMES AGENT SETUP
# ============================================================================

setup_hermes() {
    log_info "Setting up Hermes Agent..."

    if [[ -d "${HERMES_HOME}/hermes-agent" ]]; then
        log_info "Hermes already installed, skipping"
        return
    fi

    # Clone Hermes Agent
    cd "${HERMES_HOME}"
    git clone https://github.com/NousResearch/hermes-agent.git hermes-agent
    cd hermes-agent

    # Create Python virtual environment
    python3 -m venv venv
    source venv/bin/activate

    # Install Hermes
    pip install --upgrade pip
    pip install -e ".[all]"

    # Create .env file (template)
    cat > "${HERMES_HOME}/.env" <<EOF
# Core API Keys
TELEGRAM_BOT_TOKEN=
NVIDIA_API_KEY=
FAL_KEY=
FIRECRAWL_API_KEY=
OPENROUTER_API_KEY=

# Hermes API Server
API_SERVER_ENABLED=true
API_SERVER_KEY=$(generate_secret)
API_SERVER_PORT=8642
API_SERVER_HOST=127.0.0.1

# Telegram Fallback IPs
HERMES_TELEGRAM_FALLBACK_IPS=149.154.166.110,149.154.167.220,149.154.166.138,149.154.167.230

# Terminal Configuration
TERMINAL_MODAL_IMAGE=nikolaik/python-nodejs:python3.11-nodejs20
TERMINAL_TIMEOUT=60
TERMINAL_LIFETIME_SECONDS=300

# Browser
BROWSERBASE_PROXIES=true
BROWSERBASE_ADVANCED_STEALTH=false
BROWSER_SESSION_TIMEOUT=300
BROWSER_INACTIVITY_TIMEOUT=120
EOF

    chmod 600 "${HERMES_HOME}/.env"

    log_success "Hermes Agent installed"
}

setup_hermes_config() {
    log_info "Creating Hermes config.yaml..."

    cat > "${HERMES_HOME}/config.yaml" <<'EOF'
model:
  default: stepfun-ai/step-3.5-flash
  provider: nvidia
  base_url: https://integrate.api.nvidia.com/v1
  api_key: ${NVIDIA_API_KEY}

providers:
  nvidia:
    api: https://integrate.api.nvidia.com/v1
    default_model: stepfun-ai/step-3.5-flash
    models: [stepfun-ai/step-3.5-flash, minimax-m2.7]
    fallback_models: [stepfun-ai/step-3.5-flash]
  openrouter:
    api: https://openrouter.ai/api/v1
    default_model: qwen/qwen3-coder:free
    models: [qwen/qwen3-coder:free]
    fallback_models: [meta-llama/llama-3.3-70b-instruct:free]
  ollama:
    api: http://127.0.0.1:11434/v1
    default_model: granite4.1:8b
    models: [granite4.1:8b]
    fallback_models: [granite4.1:8b]

fallback_providers: [openrouter]

agent:
  max_turns: 90
  gateway_timeout: 1800
  name: Hermes
  system_prompt_path: SOUL.md
  max_tokens: 8192
  temperature: 0.7

terminal:
  backend: local
  timeout: 180
  docker_image: nikolaik/python-nodejs:python3.11-nodejs20

telegram:
  enabled: true
  bot_token: ${TELEGRAM_BOT_TOKEN}
  allowed_users: []

security:
  allow_private_urls: false
  redact_secrets: false
  tirith_enabled: true

logging:
  level: INFO
  max_size_mb: 5
  backup_count: 3

mcp_servers:
  mempalace:
    command: ${HOME}/mempalace/.venv/bin/mempalace-mcp
    args: [--palace, ${HOME}/.mempalace]
    timeout: 120

image_gen:
  model: fal-ai/flux-2/klein/9b

web:
  backend: firecrawl
  use_gateway: false
EOF

    chmod 600 "${HERMES_HOME}/config.yaml"
    log_success "Hermes config created"
}

# ============================================================================
# OPENCLAW SETUP
# ============================================================================

setup_openclaw() {
    log_info "Setting up OpenClaw..."

    if command_exists openclaw; then
        log_info "OpenClaw already installed: $(openclaw --version 2>/dev/null || echo 'unknown')"
        return
    fi

    # Install OpenClaw globally
    npm install -g openclaw

    log_success "OpenClaw installed"
}

setup_openclaw_config() {
    log_info "Creating OpenClaw config..."

    if [[ -f "${OPENCLAW_HOME}/openclaw.json" ]]; then
        log_info "OpenClaw config already exists, skipping"
        return
    fi

    cat > "${OPENCLAW_HOME}/openclaw.json" <<EOF
{
    "meta": {
        "lastTouchedVersion": "2026.5.2",
        "lastTouchedAt": "$(date -u +%Y-%m-%dT%H:%M:%S.000Z)"
    },
    "gateway": {
        "port": 18789,
        "mode": "local",
        "bind": "loopback",
        "controlUi": {
            "allowedOrigins": [
                "http://127.0.0.1:18789",
                "http://localhost:18789"
            ],
            "dangerouslyDisableDeviceAuth": true
        },
        "trustedProxies": ["127.0.0.1", "::1"],
        "auth": {
            "mode": "token",
            "token": "$(generate_secret)"
        }
    },
    "channels": {
        "telegram": {
            "enabled": false,
            "commands": {"nativeSkills": false},
            "dmPolicy": "allowlist",
            "groups": {},
            "allowFrom": [],
            "groupPolicy": "allowlist"
        }
    },
    "skills": {
        "install": {"nodeManager": "npm"}
    },
    "models": {
        "providers": {
            "ollama": {
                "baseUrl": "http://127.0.0.1:11434/v1",
                "api": "openai-completions",
                "models": []
            }
        }
    },
    "agents": {
        "defaults": {
            "workspace": "${OPENCLAW_HOME}/workspace",
            "maxConcurrent": 4,
            "sandbox": {"mode": "off"}
        },
        "list": [
            {
                "id": "main",
                "default": true,
                "name": "Main Agent",
                "workspace": "${OPENCLAW_HOME}/workspace"
            }
        ]
    }
}
EOF

    chmod 600 "${OPENCLAW_HOME}/openclaw.json"
    log_success "OpenClaw config created"
}

# ============================================================================
# OPEN DESIGN SETUP
# ============================================================================

setup_open_design() {
    log_info "Setting up Open Design..."

    if [[ -d "${USER_HOME}/open-design" ]]; then
        log_info "Open Design already exists, skipping"
        return
    fi

    # Clone Open Design (replace with actual repo)
    cd "${USER_HOME}"
    # git clone <open-design-repo-url> open-design
    # cd open-design
    # pnpm install

    log_warn "Open Design repo URL not configured. Please clone manually:"
    log_warn "  cd ${USER_HOME} && git clone <repo-url> open-design && cd open-design && pnpm install"

    log_success "Open Design setup complete"
}

# ============================================================================
# MEMPALACE SETUP
# ============================================================================

setup_mempalace() {
    log_info "Setting up MemPalace..."

    if [[ -d "${USER_HOME}/mempalace" ]]; then
        log_info "MemPalace already installed, skipping"
        return
    fi

    cd "${USER_HOME}"
    git clone https://github.com/anomalyco/mempalace.git mempalace
    cd mempalace

    # Create Python virtual environment
    python3 -m venv .venv
    source .venv/bin/activate

    # Install MemPalace
    pip install --upgrade pip
    pip install -e .

    # Initialize MemPalace
    mempalace init --palace "${MEMPALACE_HOME}"

    chmod 700 "${MEMPALACE_HOME}"

    log_success "MemPalace installed"
}

# ============================================================================
# DOCKER SERVICES
# ============================================================================

setup_docker_compose() {
    log_info "Setting up Docker Compose..."

    if [[ -f "${AI_STACK_DIR}/docker-compose.yml" ]]; then
        log_info "Docker Compose already exists, skipping"
        return
    fi

    cat > "${AI_STACK_DIR}/docker-compose.yml" <<'EOF'
services:
  open-webui:
    image: ghcr.io/open-webui/open-webui:v0.9.2
    container_name: open-webui
    ports:
      - "127.0.0.1:3000:8080"
    volumes:
      - open-webui-data:/app/backend/data
    environment:
      - OLLAMA_BASE_URL=http://host.docker.internal:11434
      - WEBUI_SECRET_KEY=${WEBUI_SECRET_KEY}
      - WEBUI_AUTH=true
      - ENABLE_SIGNUP=false
      - DEFAULT_MODELS=granite4.1:8b
      - WEBUI_NAME=Local AI
      - SCARF_NO_ANALYTICS=true
      - DO_NOT_TRACK=true
      - ANONYMIZED_TELEMETRY=false
      - ENABLE_OLLAMA_API=false
    extra_hosts:
      - "host.docker.internal:host-gateway"
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    read_only: true
    tmpfs:
      - /tmp:noexec,nosuid,size=100m
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
    deploy:
      resources:
        limits:
          memory: 2G
    logging:
      driver: json-file
      options:
        max-size: "50m"
        max-file: "3"

volumes:
  open-webui-data:
EOF

    # Create .env file
    cat > "${AI_STACK_DIR}/.env" <<EOF
WEBUI_SECRET_KEY=$(generate_secret)
EOF

    chmod 600 "${AI_STACK_DIR}/.env"

    log_success "Docker Compose configured"
}

# ============================================================================
# SYSTEMD SERVICES
# ============================================================================

setup_systemd_services() {
    log_info "Creating systemd user services..."

    mkdir -p "${SYSTEMD_DIR}"

    # Hermes Gateway Service
    cat > "${SYSTEMD_DIR}/hermes-gateway.service" <<'EOF'
[Unit]
Description=Hermes Agent Gateway - Messaging Platform Integration
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=0

[Service]
Type=simple
ExecStart=/home/lurkr/.hermes/hermes-agent/venv/bin/python -m hermes_cli.main gateway run --replace
WorkingDirectory=/home/lurkr/.hermes/hermes-agent
Environment="PATH=/home/lurkr/.hermes/hermes-agent/venv/bin:/home/lurkr/.hermes/hermes-agent/node_modules/.bin:/home/lurkr/.local/bin:/usr/local/bin:/usr/bin:/bin"
Environment="VIRTUAL_ENV=/home/lurkr/.hermes/hermes-agent/venv"
Environment="HERMES_HOME=/home/lurkr/.hermes"
Restart=always
RestartSec=60
RestartMaxDelaySec=300
RestartSteps=5
RestartForceExitStatus=75
KillMode=mixed
KillSignal=SIGTERM
ExecReload=/bin/kill -USR1 $MAINPID
TimeoutStopSec=210
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
EOF

    # Fix paths for current user
    sed -i "s|/home/lurkr|${USER_HOME}|g" "${SYSTEMD_DIR}/hermes-gateway.service"

    # Open Design Service
    cat > "${SYSTEMD_DIR}/open-design.service" <<'EOF'
[Unit]
Description=Open Design AI Stack (Daemon + Web)
After=network-online.target ollama.service
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/home/lurkr/open-design
Environment=NODE_ENV=production
Environment="PATH=/home/lurkr/.hermes/node/bin:/home/lurkr/.local/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/home/lurkr/.hermes/node/bin/pnpm tools-dev run web --daemon-port 7457 --web-port 4000
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
EOF

    # Fix paths for current user
    sed -i "s|/home/lurkr|${USER_HOME}|g" "${SYSTEMD_DIR}/open-design.service"

    # OpenClaw Gateway Service
    cat > "${SYSTEMD_DIR}/openclaw-gateway.service" <<'EOF'
[Unit]
Description=OpenClaw AI Agent Gateway
After=network-online.target ollama.service
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/home/lurkr
Environment="PATH=/home/lurkr/.hermes/node/bin:/home/lurkr/.local/bin:/usr/local/bin:/usr/bin:/bin"
EnvironmentFile=/home/lurkr/.hermes/.env
ExecStart=/home/lurkr/.hermes/node/bin/openclaw gateway run
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
EOF

    # Fix paths for current user
    sed -i "s|/home/lurkr|${USER_HOME}|g" "${SYSTEMD_DIR}/openclaw-gateway.service"

    # Enable services
    systemctl --user daemon-reload
    systemctl --user enable hermes-gateway open-design openclaw-gateway

    log_success "Systemd services created and enabled"
}

# ============================================================================
# SECURITY HARDENING
# ============================================================================

setup_security() {
    log_info "Applying security hardening..."

    # File permissions
    chmod 600 "${HERMES_HOME}/.env" 2>/dev/null || true
    chmod 600 "${HERMES_HOME}/config.yaml" 2>/dev/null || true
    chmod 600 "${OPENCLAW_HOME}/openclaw.json" 2>/dev/null || true
    chmod 600 "${AI_STACK_DIR}/.env" 2>/dev/null || true
    chmod 700 "${HERMES_HOME}" 2>/dev/null || true
    chmod 700 "${OPENCLAW_HOME}" 2>/dev/null || true
    chmod 700 "${MEMPALACE_HOME}" 2>/dev/null || true

    # Disable Ollama Docker bridge if exists
    if sudo systemctl is-active ollama-docker-bridge &>/dev/null; then
        log_warn "Disabling Ollama Docker bridge..."
        sudo systemctl disable --now ollama-docker-bridge
    fi

    # iptables firewall
    log_info "Configuring iptables..."
    sudo iptables -F INPUT
    sudo iptables -A INPUT -i lo -j ACCEPT
    sudo iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
    sudo iptables -A INPUT -p icmp -j ACCEPT
    sudo iptables -A INPUT -j DROP

    # Save iptables rules
    if command_exists iptables-save; then
        sudo iptables-save | sudo tee /etc/iptables/rules.v4 > /dev/null
    fi

    log_success "Security hardening applied"
}

# ============================================================================
# MAINTENANCE SCRIPTS
# ============================================================================

setup_maintenance_scripts() {
    log_info "Creating maintenance scripts..."

    # Backup script
    cat > "${USER_HOME}/hermes-backup.sh" <<'EOFBACKUP'
#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="/mnt/d/wslUbuntu/backups/hermes"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)

mkdir -p "${BACKUP_DIR}"

echo "Creating backup ${TIMESTAMP}..."

# Backup MemPalace
tar czf "${BACKUP_DIR}/mempalace-${TIMESTAMP}.tar.gz" -C "${HOME}" .mempalace 2>/dev/null || true

# Backup Hermes config and data
tar czf "${BACKUP_DIR}/hermes-config-${TIMESTAMP}.tar.gz" \
    -C "${HOME}" \
    .hermes/config.yaml \
    .hermes/.env \
    .hermes/state.db \
    .hermes/response_store.db \
    .hermes/sessions \
    .hermes/skills 2>/dev/null || true

# Backup OpenClaw workspace
tar czf "${BACKUP_DIR}/openclaw-workspace-${TIMESTAMP}.tar.gz" \
    -C "${HOME}" \
    .openclaw/workspace 2>/dev/null || true

# Backup Docker volume
docker run --rm -v open-webui-data:/data -v "${BACKUP_DIR}:/backup" alpine \
    tar czf "/backup/openwebui-${TIMESTAMP}.tar.gz" -C /data . 2>/dev/null || true

# Clean old backups (30 days)
find "${BACKUP_DIR}" -name "*.tar.gz" -mtime +30 -delete

echo "Backup complete: ${BACKUP_DIR}"
ls -lh "${BACKUP_DIR}"/*"${TIMESTAMP}"*
EOFBACKUP

    chmod +x "${USER_HOME}/hermes-backup.sh"

    # Health check script
    cat > "${USER_HOME}/hermes-health.sh" <<'EOFHEALTH'
#!/usr/bin/env bash
set -euo pipefail

echo "=== AI Stack Health Check ==="
echo "Date: $(date)"
echo ""

echo "=== Services ==="
systemctl --user is-active hermes-gateway &>/dev/null && echo "  Hermes: ✅" || echo "  Hermes: ❌"
systemctl --user is-active open-design &>/dev/null && echo "  Open Design: ✅" || echo "  Open Design: ❌"
systemctl --user is-active openclaw-gateway &>/dev/null && echo "  OpenClaw: ✅" || echo "  OpenClaw: ❌"
docker ps --filter name=open-webui --format '{{.Status}}' 2>/dev/null | grep -q healthy && echo "  OpenWebUI: ✅" || echo "  OpenWebUI: ❌"
sudo systemctl is-active ollama &>/dev/null && echo "  Ollama: ✅" || echo "  Ollama: ❌"

echo ""
echo "=== Ports ==="
for port in 11434 8642 7457 4000 18789 3000; do
    if ss -tlnp | grep -q "127.0.0.1:${port}"; then
        echo "  ${port}: ✅"
    else
        echo "  ${port}: ❌"
    fi
done

echo ""
echo "=== Security ==="
if ss -tlnp | grep -q "0.0.0.0"; then
    echo "  WARNING: Ports exposed on 0.0.0.0!"
else
    echo "  Ports: ✅ All localhost only"
fi

echo ""
echo "=== File Permissions ==="
for f in "${HOME}/.hermes/.env" "${HOME}/.hermes/config.yaml" "${HOME}/.openclaw/openclaw.json"; do
    if [[ -f "$f" ]]; then
        perms=$(stat -c '%a' "$f")
        if [[ "$perms" == "600" ]]; then
            echo "  $(basename $f): ✅ (${perms})"
        else
            echo "  $(basename $f): ❌ (${perms}, expected 600)"
        fi
    fi
done

echo ""
echo "=== Done ==="
EOFHEALTH

    chmod +x "${USER_HOME}/hermes-health.sh"

    log_success "Maintenance scripts created"
}

# ============================================================================
# START SERVICES
# ============================================================================

start_services() {
    log_info "Starting all services..."

    # Reload systemd
    systemctl --user daemon-reload

    # Start systemd services
    systemctl --user start hermes-gateway || log_warn "Hermes failed to start (check config)"
    systemctl --user start open-design || log_warn "Open Design failed to start (check config)"
    systemctl --user start openclaw-gateway || log_warn "OpenClaw failed to start (check config)"

    # Start Docker
    cd "${AI_STACK_DIR}"
    docker compose up -d || log_warn "Docker failed to start"

    # Wait for services
    sleep 5

    log_success "All services started"
}

# ============================================================================
# VERIFICATION
# ============================================================================

verify_setup() {
    log_info "Verifying setup..."

    local errors=0

    # Check services
    for svc in hermes-gateway open-design openclaw-gateway; do
        if ! systemctl --user is-active "$svc" &>/dev/null; then
            log_warn "Service ${svc} is not active"
            ((errors++))
        fi
    done

    # Check ports
    for port in 8642 7457 4000 18789 3000; do
        if ! ss -tlnp | grep -q "127.0.0.1:${port}"; then
            log_warn "Port ${port} not listening"
            ((errors++))
        fi
    done

    # Check Docker
    if ! docker ps --filter name=open-webui --format '{{.Status}}' 2>/dev/null | grep -q healthy; then
        log_warn "OpenWebUI container not healthy"
        ((errors++))
    fi

    if [[ $errors -eq 0 ]]; then
        log_success "All verifications passed!"
    else
        log_warn "${errors} verification(s) failed. Check logs with: journalctl --user -u <service> -f"
    fi
}

# ============================================================================
# MAIN
# ============================================================================

main() {
    echo "========================================"
    echo "  AI Agent Stack Bootloader v1.0.0"
    echo "========================================"
    echo ""

    check_root
    check_wsl

    log_info "Starting setup..."
    echo ""

    # Phase 1: System dependencies
    log_info "Phase 1: System dependencies"
    install_system_deps
    install_nodejs
    install_pnpm
    install_docker
    install_ollama
    echo ""

    # Phase 2: Directory structure
    log_info "Phase 2: Directory structure"
    create_directories
    echo ""

    # Phase 3: Agent frameworks
    log_info "Phase 3: Agent frameworks"
    setup_hermes
    setup_hermes_config
    setup_openclaw
    setup_openclaw_config
    setup_open_design
    setup_mempalace
    echo ""

    # Phase 4: Docker services
    log_info "Phase 4: Docker services"
    setup_docker_compose
    echo ""

    # Phase 5: Systemd services
    log_info "Phase 5: Systemd services"
    setup_systemd_services
    echo ""

    # Phase 6: Security
    log_info "Phase 6: Security hardening"
    setup_security
    echo ""

    # Phase 7: Maintenance
    log_info "Phase 7: Maintenance scripts"
    setup_maintenance_scripts
    echo ""

    # Phase 8: Start services
    log_info "Phase 8: Starting services"
    start_services
    echo ""

    # Phase 9: Verify
    log_info "Phase 9: Verification"
    verify_setup
    echo ""

    echo "========================================"
    echo "  Setup Complete!"
    echo "========================================"
    echo ""
    echo "Next steps:"
    echo "  1. Edit ${HERMES_HOME}/.env with your API keys"
    echo "  2. Edit ${AI_STACK_DIR}/.env if needed"
    echo "  3. Run ~/hermes-health.sh to verify"
    echo "  4. Pull Ollama models: ollama pull granite4.1:8b"
    echo "  5. Restart services: systemctl --user restart hermes-gateway openclaw-gateway"
    echo ""
}

main "$@"
