"""Model provider health checks for Ollama, NVIDIA, and OpenAI."""
import asyncio
import aiohttp
import os
from typing import Any, Dict, List, Optional

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")


async def _http_get(url: str, timeout: int = 5) -> Optional[Dict[str, Any]]:
    """GET JSON from URL, return None on failure."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                if resp.status == 200:
                    return await resp.json()
    except Exception:
        pass
    return None


async def check_ollama() -> Dict[str, Any]:
    """Check Ollama health + list models."""
    data = await _http_get(f"{OLLAMA_HOST}/api/version")
    if data is not None:
        models = await _http_get(f"{OLLAMA_HOST}/api/tags")
        model_names = [m["name"] for m in models.get("models", [])] if models else []
        return {
            "provider": "ollama",
            "status": "healthy",
            "version": data.get("version", "unknown"),
            "models": model_names,
            "url": OLLAMA_HOST,
        }
    return {"provider": "ollama", "status": "unreachable", "url": OLLAMA_HOST}


def check_nvidia() -> Dict[str, Any]:
    """Check NVIDIA GPU via nvidia-smi."""
    import subprocess
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            vals = result.stdout.strip().split(", ")
            return {
                "provider": "nvidia",
                "status": "healthy",
                "gpu_util": float(vals[0].strip()),
                "memory_used_mb": float(vals[1].strip()),
                "memory_total_mb": float(vals[2].strip()),
            }
        return {"provider": "nvidia", "status": "error", "detail": result.stderr.strip()}
    except FileNotFoundError:
        return {"provider": "nvidia", "status": "not_found"}
    except Exception as e:
        return {"provider": "nvidia", "status": "error", "detail": str(e)}


async def check_openai() -> Dict[str, Any]:
    """Check OpenAI API key validity."""
    if not OPENAI_API_KEY:
        return {"provider": "openai", "status": "not_configured", "detail": "OPENAI_API_KEY not set"}
    try:
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
            async with session.get(
                "https://api.openai.com/v1/models",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    models = [m["id"] for m in data.get("data", [])[:10]]
                    return {
                        "provider": "openai",
                        "status": "healthy",
                        "model_count": len(data.get("data", [])),
                        "available_models": models,
                    }
                elif resp.status == 401:
                    return {"provider": "openai", "status": "auth_error", "detail": "Invalid API key"}
                else:
                    return {"provider": "openai", "status": "error", "detail": f"HTTP {resp.status}"}
    except Exception as e:
        return {"provider": "openai", "status": "error", "detail": str(e)}


async def check_all_providers() -> List[Dict[str, Any]]:
    """Check all providers and return results."""
    ollama_result = await check_ollama()
    nvidia_result = check_nvidia()
    openai_result = await check_openai()
    return [ollama_result, nvidia_result, openai_result]