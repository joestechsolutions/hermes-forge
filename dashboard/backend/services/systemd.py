import asyncio
import json
from pathlib import Path
from typing import Dict, List, Any

async def check_systemd_service(name: str) -> Dict[str, Any]:
    proc = await asyncio.create_subprocess_exec(
        "systemctl", "--user", "show", name,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, _ = await proc.communicate()
    if proc.returncode == 0:
        data = {}
        for line in stdout.decode().split('\n'):
            if '=' in line:
                k, v = line.split('=', 1)
                data[k] = v
        return {
            "name": name,
            "state": data.get("ActiveState", "unknown"),
            "uptime": data.get("ActiveEnterTimestamp", None)
        }
    return {"name": name, "state": "failed", "error": "service not found"}

async def check_docker_containers() -> List[Dict]:
    proc = await asyncio.create_subprocess_exec(
        "docker", "ps", "-a", "--format", "json",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, _ = await proc.communicate()
    containers = []
    for line in stdout.decode().strip().split('\n'):
        if line:
            try:
                c = json.loads(line)
                containers.append({
                    "name": c.get("Names", "unknown"),
                    "state": c.get("State", "unknown"),
                    "port": extract_port(c.get("Ports", ""))
                })
            except json.JSONDecodeError:
                continue
    return containers

def extract_port(port_str: str) -> int | None:
    import re
    match = re.search(r":(\d+)->", port_str)
    if match:
        return int(match.group(1))
    return None

async def tail_systemd_logs(service: str, lines: int = 100) -> List[str]:
    proc = await asyncio.create_subprocess_exec(
        "journalctl", "--user", "-u", service, "-n", str(lines), "--no-pager",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, _ = await proc.communicate()
    return stdout.decode().split('\n') if stdout else []

async def run_systemctl_command(service: str, action: str) -> Dict[str, Any]:
    proc = await asyncio.create_subprocess_exec(
        "systemctl", "--user", action, service,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    return {
        "returncode": proc.returncode,
        "stdout": stdout.decode(),
        "stderr": stderr.decode()
    }

async def run_security_audit() -> List[Dict[str, Any]]:
    checks = []
    # Port binding check
    proc = await asyncio.create_subprocess_exec("ss", "-tlnp", stdout=asyncio.subprocess.PIPE)
    stdout, _ = await proc.communicate()
    output = stdout.decode()
    exposed = False
    for line in output.split('\n'):
        if 'LISTEN' in line and ('0.0.0.0:' in line or ':::' in line):
            exposed = True
            checks.append({"check": "Port exposure", "pass": False, "details": f"Port exposed on all interfaces: {line.strip()}"})
            break
    if not exposed:
        checks.append({"check": "Port exposure", "pass": True, "details": "All listening ports on localhost only"})

    # File permissions
    critical_files = [
        Path.home() / ".hermes/.env",
        Path.home() / ".hermes/config.yaml",
        Path.home() / ".openclaw/openclaw.json",
        Path.home() / ".opencode/opencode.json",
        Path.home() / ".mempalace/config.json",
        Path("/srv/ai-stack/docker-compose.yml"),
        Path("/srv/ai-stack/.env")
    ]
    for f in critical_files:
        if f.exists():
            perms = oct(f.stat().st_mode)[-3:]
            checks.append({"check": f"File perm: {f.name}", "pass": perms == "600", "details": f"{perms}"})
        else:
            checks.append({"check": f"File exists: {f.name}", "pass": False, "details": "Missing"})

    # Ollama bridge check
    try:
        proc = await asyncio.create_subprocess_exec("ss", "-tlnp", stdout=asyncio.subprocess.PIPE)
        stdout, _ = await proc.communicate()
        if b'172.17.0.1:11434' in stdout or b'0.0.0.0:11434' in stdout:
            checks.append({"check": "Ollama bridge", "pass": False, "details": "Bridge detected"})
        else:
            checks.append({"check": "Ollama bridge", "pass": True, "details": "No bridge"})
    except Exception:
        checks.append({"check": "Ollama bridge", "pass": False, "details": "ss failed"})

    return checks

async def validate_all_configs() -> List[Dict[str, Any]]:
    results = []
    config_files = [
        Path.home() / ".hermes/config.yaml",
        Path.home() / ".hermes/.env",
        Path.home() / ".openclaw/openclaw.json",
        Path.home() / ".opencode/opencode.json",
        Path("/srv/ai-stack/docker-compose.yml"),
        Path("/srv/ai-stack/.env")
    ]
    for f in config_files:
        if not f.exists():
            results.append({"file": str(f), "valid": False, "error": "File not found"})
            continue
        try:
            if f.suffix in ['.yaml', '.yml']:
                import yaml
                with open(f) as fp:
                    yaml.safe_load(fp)
            elif f.suffix == '.json':
                with open(f) as fp:
                    json.load(fp)
            elif f.name == '.env':
                with open(f) as fp:
                    for line in fp:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' not in line:
                            raise ValueError("Invalid line")
            else:
                continue
            results.append({"file": str(f), "valid": True})
        except Exception as e:
            results.append({"file": str(f), "valid": False, "error": str(e)})
    return results
