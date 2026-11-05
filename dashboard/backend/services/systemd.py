"""Live systemd/Docker inventory and bounded log/action helpers."""
import asyncio
import json
import re
from pathlib import Path
from typing import Any

CORE_SERVICES = (
    "hermes-gateway", "hermes-serve", "open-design", "free-claude-code",
    "dashboard-backend", "cc-tunnel", "memguard", "lurkr-sync",
    "matraix-playground-api", "matraix-playground-ui",
)
MANAGED_PREFIXES = (
    "hermes-", "cc-", "dashboard-", "matraix-", "memguard", "lurkr-sync",
    "open-design", "free-claude-code", "second-brain",
)


async def _run(*args: str, timeout: float = 10) -> tuple[int, str, str]:
    try:
        proc = await asyncio.create_subprocess_exec(
            *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return proc.returncode or 0, stdout.decode(errors="replace"), stderr.decode(errors="replace")
    except (OSError, asyncio.TimeoutError) as exc:
        return 1, "", str(exc)


async def managed_service_names() -> list[str]:
    """Discover JTS/Hermes units so new services appear without a code edit."""
    code, stdout, _ = await _run(
        "systemctl", "--user", "list-units", "--type=service", "--all",
        "--output=json", "--no-pager"
    )
    names: set[str] = set(CORE_SERVICES)
    if code == 0:
        try:
            for row in json.loads(stdout):
                unit = row.get("unit") or row.get("UnitName") or ""
                name = unit.removesuffix(".service")
                if name.startswith(MANAGED_PREFIXES):
                    names.add(name)
        except (ValueError, TypeError, AttributeError):
            pass
    return sorted(names)


async def check_systemd_service(name: str) -> dict[str, Any]:
    code, stdout, _ = await _run("systemctl", "--user", "show", name, "--no-pager")
    data = dict(line.split("=", 1) for line in stdout.splitlines() if "=" in line)
    if code != 0:
        return {"name": name, "state": "unavailable"}
    return {
        "name": name,
        "state": "not_found" if data.get("LoadState") == "not-found" else data.get("ActiveState", "unknown"),
        "uptime": data.get("ActiveEnterTimestamp") or None,
    }


async def check_docker_containers() -> list[dict[str, Any]]:
    code, stdout, _ = await _run("docker", "ps", "-a", "--format", "json")
    containers = []
    if code != 0:
        return containers
    for line in stdout.splitlines():
        try:
            c = json.loads(line)
            containers.append({
                "name": c.get("Names", "unknown"),
                "state": c.get("State", "unknown"),
                "kind": "docker",
                "port": extract_port(c.get("Ports", "")),
            })
        except (ValueError, TypeError):
            continue
    return containers


def extract_port(port_str: str) -> int | None:
    match = re.search(r":(\d+)->", port_str)
    return int(match.group(1)) if match else None


async def tail_systemd_logs(service: str, lines: int = 100) -> list[str]:
    _, stdout, _ = await _run(
        "journalctl", "--user", "-u", service, "-n", str(lines), "--no-pager"
    )
    return stdout.splitlines()


async def tail_docker_logs(service: str, lines: int = 100) -> list[str]:
    _, stdout, stderr = await _run("docker", "logs", "--tail", str(lines), service)
    return (stdout + stderr).splitlines()


async def run_systemctl_command(service: str, action: str) -> dict[str, Any]:
    code, stdout, stderr = await _run("systemctl", "--user", action, service, timeout=20)
    return {"returncode": code, "stdout": stdout, "stderr": stderr}


async def run_security_audit() -> list[dict[str, Any]]:
    checks = []
    code, output, _ = await _run("ss", "-tlnp")
    exposed = []
    if code == 0:
        for line in output.splitlines():
            if "LISTEN" not in line:
                continue
            match = re.search(r"([0-9a-f:.]+|\d+\.\d+\.\d+\.\d+):\d+", line)
            if match and match.group(1) in ("0.0.0.0", "::", "[::]"):
                # Report only the bind/port, not process command lines or environment.
                exposed.append(match.group(0))
        checks.append({
            "check": "Port exposure", "pass": not exposed,
            "details": "No listeners on all interfaces" if not exposed else f"Public bind(s): {', '.join(exposed)}",
        })
    else:
        checks.append({"check": "Port exposure", "pass": False, "details": "Could not inspect listening ports"})

    for path in (
        Path.home() / ".hermes/.env", Path.home() / ".hermes/config.yaml",
        Path.home() / ".opencode/opencode.json", Path.home() / ".mempalace/config.json",
        Path("/srv/ai-stack/docker-compose.yml"), Path("/srv/ai-stack/.env"),
    ):
        if path.exists():
            mode = path.stat().st_mode & 0o777
            checks.append({
                "check": f"File permission: {path.name}", "pass": mode == 0o600,
                "details": f"Current mode: {mode:03o}",
            })
        else:
            checks.append({"check": f"Optional config: {path.name}", "pass": True, "details": "Not present"})

    checks.append({
        "check": "Ollama bridge", "pass": code == 0 and "0.0.0.0:11434" not in output and "172.17.0.1:11434" not in output,
        "details": "No public Ollama bridge detected" if code == 0 else "Could not inspect bridge",
    })
    return checks


async def validate_all_configs() -> list[dict[str, Any]]:
    import yaml
    results = []
    for path in (
        Path.home() / ".hermes/config.yaml", Path.home() / ".hermes/.env",
        Path.home() / ".opencode/opencode.json", Path("/srv/ai-stack/docker-compose.yml"),
        Path("/srv/ai-stack/.env"),
    ):
        if not path.exists():
            results.append({"file": str(path), "valid": True, "status": "not_present"})
            continue
        try:
            if path.suffix in (".yaml", ".yml"):
                yaml.safe_load(path.read_text())
            elif path.suffix == ".json":
                json.loads(path.read_text())
            elif path.name == ".env":
                for line in path.read_text().splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "=" not in line:
                        raise ValueError("Invalid environment-file line")
            results.append({"file": str(path), "valid": True})
        except Exception as exc:
            results.append({"file": str(path), "valid": False, "error": str(exc)})
    return results
