User is Hyphy. Machine is joBlade (WSL2 Ubuntu). User is recovering from a C: drive transfer disaster that corrupted the WSL Ubuntu environment. Successfully restored Hermes Agent (Lurkr) with Telegram integration using @lurkr_windows_bot.
§
Full AI Platform architecture is operational as of 2026-05-05: Hermes Gateway (Telegram + API), OpenClaw Gateway, Open Design (daemon + web), OpenWebUI (Docker), and Ollama (local LLM). All services verified working and interconnected. Blueprint stored at ~/ai-platform/ and backed up to /mnt/d/wslUbuntu/ai-platform-backup/.
§
Ollama models stored on Linux filesystem at /var/lib/ollama/ (NOT /mnt/d/ Windows drive). Windows NTFS causes 2+ minute model load times that timeout. Service runs as user lurkr (not ollama). RTX 2060 6GB GPU available. granite4.1:8b model loaded. Load time ~133s first load, stays in memory 5min.
§
Hermes handles Telegram exclusively. OpenClaw Telegram disabled in openclaw.json to prevent token conflict. Both cannot use same bot token simultaneously.
§
Security hardened: iptables DROP policy, all services bind 127.0.0.1 only, Ollama Docker bridge disabled, file permissions 600/700, Docker containers with no-new-privileges and cap_drop ALL.
§
Model providers: NVIDIA NIM primary (stepfun-ai/step-3.5-flash, minimax-m2.7), OpenRouter fallback (qwen/qwen3-coder:free, nemotron variants), Ollama local (granite4.1:8b). OpenClaw uses Anthropic Claude, Google Gemini, and OpenRouter models.
§
Full infrastructure documentation: ~/.hermes/memories/INFRASTRUCTURE.md
