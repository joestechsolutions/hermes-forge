# Hermes Infrastructure Suite — Diagnostic Dashboard & Bootloader

> [!NOTE]
> **Spec Version:** 1.0.0 | **Date:** 2026-05-10 | **Author:** Lurkr (via Claude Code) | **Status:** Draft

---

## 📑 Table of Contents
- [1. Overview](#1-overview)
- [2. Diagnostic Dashboard](#2-diagnostic-dashboard)
  - [2.1 Product Vision](#21-product-vision)
  - [2.2 Architecture](#22-architecture)
  - [2.3 UI Design](#23-ui-design)
  - [2.4 API Endpoints](#24-api-endpoints)
  - [2.5 State Management](#25-state-management)
  - [2.6 Error Handling](#26-error-handling)
- [3. Bootloader](#3-bootloader)
  - [3.1 Product Vision](#31-product-vision)
  - [3.3 Plugin Architecture](#33-plugin-architecture)
  - [3.5 Snapshot System](#35-snapshot-system)
  - [3.7 Required Plugins](#37-required-plugins)
- [4. Shared Infrastructure](#4-shared-infrastructure)
- [5. Implementation Plan](#5-implementation-order-phased)
- [6. Testing Strategy](#6-testing-strategy)
- [7. Open Questions](#7-open-questions)

---

## 1. Overview

Two independent products with a shared mission: give Lurkr/Joe a full observability and control surface over the Hermes agentic stack.

| Product | Purpose | Location | Target Persona |
| :--- | :--- | :--- | :--- |
| **Diagnostic Dashboard** | Live monitoring + operations GUI | `github.com/joblas/Lurkr-Jo-Blade-Hermes` | Day-2 ops, daily use |
| **Bootloader** | Single-command provisioning | `bootloader/` subdirectory | DR, new machine setup |

> [!IMPORTANT]
> **Bootloader and Dashboard are independent.** No install dependency. Use the Bootloader once for setup; keep the Dashboard running 24/7 as mission control.

---

## 2. Diagnostic Dashboard

### 2.1 Product Vision
A real-time, war-room command center styled in **cyberpunk/HUD aesthetic**. It synthesizes the existing Hermes and OpenClaw gateways into a single unified view surfacing the **whole stack** at once: agent frameworks, gateways, model providers, and system services.

### 2.2 Architecture

```text
┌──────────────────────────────────────────────────────────────┐
│         Diagnostic Dashboard — React + TypeScript           │
│              (port 8643, localhost browser)                │
└──────────────────────────┬─────────────────────────────────┘
                           │ REST (polling) + WebSocket (live metrics)
┌──────────────────────────▼─────────────────────────────────┐
│        Diagnostic Dashboard — FastAPI Backend               │
│                (port 8643, localhost)                     │
│                                                              │
│  services/                                                  │
│    ├── system_metrics.py   — psutil CPU/Mem/Disk/GPU       │
│    ├── systemd_status.py   — systemctl --user list-units    │
│    ├── docker_status.py    — docker ps --format json         │
│    ├── logs.py             — journalctl --user -u <svc> -n   │
│    ├── model_providers.py  — health-check NVIDIA/Ollama/OAI  │
│    ├── agent_status.py     — CLI probes for OpenCode,        │
│    │                         Claude Code, MemPalace state     │
│    ├── snapshot_manager.py — state_manager.load/apply       │
│    └── security_audit.py  — port exposure, perms, iptables   │
│                                                              │
│  api/routes.py     — /api/v1/* REST endpoints                │
│  api/ws_metrics.py — /ws/metrics broadcast via asyncio      │
└─────────────────────────────────────────────────────────────┘
        │                              │
        │ (only reads state,          │ (already running,
        │  does not restart systems)    │ Hermes/OpenClaw control)
        ▼                              ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐
│ hermes-agent │  │ openclaw     │  │ systemd user services     │
│ (port 8642)  │  │ (port 18789) │  │ hermes-gateway,          │
└──────────────┘  └──────────────┘  │ openclaw-gateway,       │
        │              │             │ open-design,            │
        ▼              ▼             │ dashboard-backend         │
┌──────────────────────────┐       └──────────────────────────┘
│ ollama (11434)            │
│ nvidia-smi               │
│ ~/.hermes/state.db        │
│ ~/.hermes/snapshots/      │
└──────────────────────────┘
```

> [!TIP]
> **Key design decision:** The Dashboard backend is the aggregation layer. It polls each sub-system and exposes everything through a unified FastAPI interface. No changes to Hermes agent or OpenClaw are required.

### 2.3 UI Design

**Color Palette (Cyberpunk Aesthetic):**
*   **Background:** `#060606` (Near-black)
*   **Active/Healthy:** `#00dc82` (Hermes Green)
*   **Degraded:** `#f59e0b` (Amber)
*   **Offline/Failed:** `#ef4444` (Red)
*   **Data Highlight:** `#00b4f5` (Cyan)

**Layout Navigation:**
1.  **Mission Control:** Primary real-time grid view.
2.  **Services:** Systemd + Docker management.
3.  **Providers:** API key health and latency checks.
4.  **Snapshots:** State management (Create/List/Restore).
5.  **Security:** Real-time port and permission audit.

### 2.4 API Endpoints
All routes are prefixed with `/api/v1`.

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/services` | List all systemd + Docker services |
| `POST` | `/services/{name}/start` | Start a specific service |
| `GET` | `/logs/{service}` | Tail logs (default 100 lines) |
| `GET` | `/agents/hermes` | Hermes status (state.db + health) |
| `GET` | `/providers` | Model provider health stats |
| `WS` | `/ws/metrics` | Stream metrics every 2s |

### 2.5 State Management
*   **MetricsContext:** WebSocket-driven live metrics (2s interval).
*   **ServicesContext:** Polled service states (10s interval).
*   **Provider Health:** Live checks (30s interval).

---

## 3. Bootloader

### 3.1 Product Vision
A single-command, **idempotent**, and recoverable provisioning tool. It follows a 4-phase lifecycle: `prereq` → `install` → `verify` → `cleanup`.

### 3.3 Plugin Architecture
Every plugin is a Python module in `bootloader/plugins/` implementing standard hooks:

```python
def hook_check_prerequisites(context: Dict[str, Any]) -> bool: ...
def hook_install(context: Dict[str, Any]) -> Dict[str, Any]: ...
def hook_verify(context: Dict[str, Any]) -> bool: ...
```

### 3.5 Snapshot System
The `StateManager` captures:
1.  **Configs:** Base64-encoded file contents + SHA256.
2.  **Services:** Current systemd user service states.
3.  **Infrastructure:** Ollama models and Docker containers.

### 3.7 Required Plugins

| Plugin | Status | Responsible for |
| :--- | :--- | :--- |
| `system_deps` | ✅ | Core apt packages |
| `pnpm` | 🆕 | global npm install |
| `openclaw` | 🆕 | Repo setup + service config |
| `mempalace` | 🆕 | Git clone + venv setup |
| `security_hardening` | 🆕 | iptables & permissions |

---

## 4. Shared Infrastructure

**Repository Layout:**
```text
Lurkr-Jo-Blade-Hermes/
├── bootloader/            — Python provisioning tool
│   ├── plugins/           — Step-by-step install scripts
│   └── lib/               — State & Plugin managers
├── dashboard/             — Real-time GUI
│   ├── backend/           — FastAPI (Python)
│   └── frontend/          — React + Vite (Node)
├── configs/               — Systemd & Service templates
└── docs/                  — Architecture & Reference
```

---

## 5. Implementation Order (Phased)

### Phase 1: Foundation
*   Repository structure setup.
*   CI/CD (GitHub Actions) for linting and testing.
*   Daily cron backup configuration.

### Phase 2: Bootloader Completion
*   Develop the 10 missing plugin files.
*   Implement `bootstrap.sh` for fresh machines.
*   End-to-end verification in WSL.

### Phase 3 & 4: Dashboard
*   **Backend:** Service modules for systemd/docker/logs.
*   **Frontend:** React components with Tailwind + Cyberpunk theme.
*   **Real-time:** WebSocket integration for Mission Control.

---

## 6. Testing Strategy

*   **Bootloader:** Pytest suite with mocked subprocesses (no real installs during CI).
*   **Backend:** FastAPI `TestClient` for all routes; mocked hardware responses.
*   **Frontend:** `@testing-library/react` for component integrity.

---

## 7. Open Questions

> [!CAUTION]
> **1. Provider Health:** Should checks be fresh or cached? *Decision: Fresh with 30s TTL.*
>
> **2. Claude Code Probe:** How to check status without an API? *Decision: pgrep + session dir parsing.*
>
> **3. Deployment:** Single binary vs. Split? *Decision: Backend serves frontend static files.*

---

## 8. Constraints & Non-Goals

*   **In Scope:** Monitoring, systemd management, snapshots, local-first operation.
*   **Out of Scope:** Cloud/K8s deployment, Multi-user authentication, Long-term metrics persistence.