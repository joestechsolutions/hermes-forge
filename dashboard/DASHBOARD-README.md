# Hermes Infrastructure Dashboard

## Overview

The Hermes Infrastructure Dashboard provides real-time monitoring and control of the Hermes Agent ecosystem and associated services. It displays live system metrics, service status, logs, and allows actions like start/stop/restart, snapshot management, and security auditing.

## Features

- **Live Metrics**: CPU, Memory, Disk, and GPU utilization updated every 2 seconds via WebSocket.
- **Service Management**: View status of systemd and Docker services; start, stop, restart.
- **Log Viewer**: Tail logs from any systemd service (e.g., hermes-gateway, openclaw-gateway, docker containers).
- **Snapshot Control**: Create and restore system snapshots using the Bootloader's state manager.
- **Security Audit**: Review port binding, file permissions, container security, and Ollama bridge exposure.
- **Configuration Validation**: Check all critical config files for syntax errors.
- **Dark Theme**: Hermes-branded dark UI built with Tailwind CSS.

## Architecture

### Backend (FastAPI)

- **Port**: 8643 (localhost only)
- **Main App**: `~/ai-platform/dashboard/backend/main.py`
- **API**: REST endpoints under `/api/v1` plus WebSocket `/ws/metrics`
- **Static Files**: Serves the built frontend from `~/ai-platform/dashboard/frontend/dist/` if present.

### Frontend (React + TypeScript + Vite)

- **Dev Server**: Vite on port 5173 (proxying API to 8643, WS to 8643)
- **Build**: `npm run build` outputs to `frontend/dist`
- **Dependencies**: React 18, Tailwind CSS, Axios.

## Installation

### Via Bootloader (Recommended)

The Bootloader will install the dashboard as part of the standard setup:

```bash
cd ~/ai-platform/bootloader
./bootloader.sh run --phase all
```

The `dashboard` plugin will:
- Install backend Python requirements (`pip install --user -r backend/requirements.txt`)
- Install frontend dependencies (`npm ci`) and build (`npm run build`)
- Install the systemd user service `dashboard-backend.service`
- Enable and start the service.

### Manual Setup

1. **Backend**:

```bash
cd ~/ai-platform/dashboard/backend
pip3 install --user -r requirements.txt
systemctl --user enable ~/ai-platform/dashboard/backend/systemd/dashboard-backend.service
systemctl --user start dashboard-backend
```

2. **Frontend**:

```bash
cd ~/ai-platform/dashboard/frontend
npm ci
npm run build
```

The backend will serve the built frontend at `http://127.0.0.1:8643`.

## Usage

Open your browser at `http://127.0.0.1:8643`.

- **Metrics Bar** (top) shows live system stats.
- **Service Cards** display state, port, uptime, last log. Buttons to Start/Stop/Restart.
- Click a card to open a **Logs Viewer** modal tailing journalctl for that service.
- **Snapshot** operations can be accessed via additional UI (to be added).

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/services` | GET | List all monitored services (systemd + Docker) |
| `/api/v1/logs/{service}` | GET | Tail logs (query param `lines`) |
| `/api/v1/services/{service}/restart` | POST | Restart a service |
| `/api/v1/services/{service}/start` | POST | Start a service |
| `/api/v1/services/{service}/stop` | POST | Stop a service |
| `/api/v1/snapshots` | GET | List available snapshots |
| `/api/v1/snapshots` | POST | Create snapshot (`{ "name": "..." }`) |
| `/api/v1/snapshots/{name}/restore` | POST | Restore a snapshot |
| `/api/v1/security/status` | GET | Run security audit |
| `/api/v1/config/validate` | POST | Validate all config files |
| `/ws/metrics` | WS | Stream live system metrics every 2 seconds |

## Troubleshooting

- **Backend not reaching**: `journalctl --user -u dashboard-backend -f`
- **Services not showing**: Check `bootloader` state; run `./bootloader.sh run --phase install`
- **CORS errors**: The backend is configured to allow `localhost:5173` and `127.0.0.1:8643`.
- **Permission issues**: All sensitive configs expect 600 permissions. Use `chmod 600 ~/.hermes/.env` etc.

## Development

```bash
cd ~/ai-platform/dashboard/frontend
npm run dev   # starts Vite on 5173 with API proxy
```

```bash
cd ~/ai-platform/dashboard/backend
python3 -m main   # runs uvicorn on 8643
```
