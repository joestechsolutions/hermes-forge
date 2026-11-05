"""Command Center service — aggregates Hermes cron reports for the dashboard Briefings tab.

Data sources (read-only):
  ~/.hermes/cron/jobs.json            — 50 live cron jobs (schedule, status, next run)
  ~/.hermes/cron/output/<jobid>/*.md  — report files (header + ## Response body)
  ~/.hermes/cron/state/*.state        — misc state files (sizes only)

Design notes:
- jobs.json is a JSON object {jobs: [...]} OR a bare list; both shapes handled.
- Report files embed the prompt echo; the human-readable body lives after '## Response'.
- Categories derived from job name heuristics (vp_/cfo/cos/cmo = leadership,
  renfaire/skate/steward = clients, weekly/monthly = reviews, rest = ops).
"""
import json
import os
import re
import glob
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

CRON_DIR = os.path.expanduser("~/.hermes/cron")
JOBS_FILE = os.path.join(CRON_DIR, "jobs.json")
OUTPUT_DIR = os.path.join(CRON_DIR, "output")


def _load_jobs() -> List[Dict[str, Any]]:
    with open(JOBS_FILE, errors="ignore") as f:
        d = json.load(f)
    if isinstance(d, list):
        return [j for j in d if isinstance(j, dict)]
    for v in d.values():
        if isinstance(v, list):
            return [j for j in v if isinstance(j, dict)]
    return []


def _active(job: Dict[str, Any]) -> bool:
    return bool(job.get("enabled")) and job.get("state") not in ("paused", "completed")


def _failed(job: Dict[str, Any]) -> bool:
    return (job.get("failure_streak", 0) or 0) > 0 or job.get("last_status") not in ("ok", "success", None)


def _category(name: str, schedule_expr: str) -> str:
    n = name.lower()
    if any(k in n for k in ("vp_", "cfo", "coo", "cos_", "cmo", "chief")):
        return "Leadership"
    if any(k in n for k in ("renfaire", "skate", "steward", "nick", "archive_salon", "cbarrgs", "fairway")):
        return "Clients"
    if any(k in n for k in ("watch", "monitor", "uptime", "health", "probe", "security")):
        return "Ops & Health"
    if any(k in n for k in ("content", "draft", "ig_", "maps_", "seo", "gsc", "radar")):
        return "Content & Growth"
    if any(k in n for k in ("weekly", "monthly", "review", "audit", "scorecard", "sprint")):
        return "Reviews"
    if any(k in n for k in ("backup", "vault", "mempalace", "wiki", "kg_", "librarian")):
        return "Memory & Backup"
    return "Daily Run"


def _cadence(schedule: Dict[str, Any]) -> str:
    expr = schedule.get("expr", "") if isinstance(schedule, dict) else ""
    kind = str(schedule.get("kind", "")).lower()
    display = str(schedule.get("display", ""))
    if kind in ("every", "interval") or display.lower().startswith("every"):
        return display or "interval"
    parts = expr.split()
    if len(parts) >= 5:
        minute, hour, dom, mon, dow = parts[:5]
        if expr == "* * * * *":
            return "every minute"
        if minute.startswith("*/") and hour == "*":
            return f"every {minute[2:]}m"
        if hour.startswith("*/") and dom == "*" and dow == "*":
            return f"every {hour[2:]}h"
        if dom != "*" and dom != "*/1":
            return "monthly"
        if dow != "*":
            d = dow.replace("0", "7")
            return "weekdays" if d in ("1-5", "1,2,3,4,5") else "weekly"
        return "daily"
    return display or "periodic"


def _latest_output(job_id: str) -> Optional[Dict[str, Any]]:
    d = os.path.join(OUTPUT_DIR, job_id)
    if not os.path.isdir(d):
        return None
    files = sorted(glob.glob(os.path.join(d, "*.md")), key=os.path.getmtime, reverse=True)
    flat = sorted(glob.glob(os.path.join(OUTPUT_DIR, f"{job_id[:12]}*.md")) if os.path.isdir(OUTPUT_DIR) else [],
                  key=os.path.getmtime, reverse=True)
    files = files or flat
    if not files:
        return None
    f = files[0]
    try:
        s = open(f, errors="ignore").read()
    except OSError:
        return None
    mtime = datetime.fromtimestamp(os.path.getmtime(f)).isoformat(timespec="seconds")
    # human body after '## Response' / '## Output'; fall back to raw tail
    i = s.rfind("## Response")
    if i == -1:
        i = s.rfind("## Output")
    if i > -1:
        body = s[i:].strip()
        body = body.split("\n", 1)[1].strip() if "\n" in body else body
    else:
        body = s[-1500:]
    body = re.sub(r"\n{3,}", "\n\n", body)
    return {"file": os.path.basename(f), "mtime": mtime, "size": len(s), "body": body[:12000]}


def list_jobs(category: Optional[str] = None, include_outputs: bool = False) -> Dict[str, Any]:
    jobs = _load_jobs()
    out = []
    for j in jobs:
        name = j.get("name", "?")
        sched = j.get("schedule", {})
        item: Dict[str, Any] = {
            "id": j.get("id"),
            "name": name,
            "enabled": _active(j),
            "state": j.get("state"),
            "model": j.get("model"),
            "category": _category(name, sched.get("expr", "") if isinstance(sched, dict) else ""),
            "cadence": _cadence(sched),
            "cron_expr": (sched.get("expr") if isinstance(sched, dict) else None) or sched.get("display"),
            "last_status": j.get("last_status"),
            "last_run_at": j.get("last_run_at"),
            "next_run_at": j.get("next_run_at"),
            "failure_streak": j.get("failure_streak", 0),
            "paused_reason": j.get("paused_reason"),
        }
        if include_outputs:
            item["latest"] = _latest_output(j.get("id", ""))
        out.append(item)
    if category:
        out = [j for j in out if j["category"] == category]
    return {"jobs": out, "count": len(out)}


def categories() -> List[Dict[str, Any]]:
    jobs = _load_jobs()
    cats: Dict[str, Dict[str, int]] = {}
    for j in jobs:
        if not isinstance(j, dict):
            continue
        c = _category(j.get("name", "?"), "")
        slot = cats.setdefault(c, {"total": 0, "live": 0, "failing": 0})
        slot["total"] += 1
        if _active(j):
            slot["live"] += 1
            if _failed(j):
                slot["failing"] += 1
    return [{"category": k, **v} for k, v in sorted(cats.items())]


def recent_reports(limit: int = 12) -> List[Dict[str, Any]]:
    idmap = {j.get("id"): j.get("name", "?") for j in _load_jobs()}
    # collect md files under per-job dirs + flat output files
    files = glob.glob(os.path.join(OUTPUT_DIR, "*", "*.md")) + glob.glob(os.path.join(OUTPUT_DIR, "*.md")) + \
            glob.glob(os.path.join(OUTPUT_DIR, "*", "*.txt"))
    files = [f for f in files if os.path.isfile(f)]
    files.sort(key=os.path.getmtime, reverse=True)
    out, seen = [], set()
    for f in files:
        jid = os.path.basename(os.path.dirname(f)) if os.path.basename(os.path.dirname(f)) != "output" else ""
        name = idmap.get(jid) or idmap.get(jid[:12]) or jid or os.path.basename(f).split("_")[0]
        # dedupe per job: keep latest only
        key = jid or name
        if key in seen:
            continue
        seen.add(key)
        try:
            s = open(f, errors="ignore").read()
        except OSError:
            continue
        i = s.rfind("## Response")
        if i == -1:
            i = s.rfind("## Output")
        if i > -1:
            body = s[i:].strip()
            body = body.split("\n", 1)[1].strip() if "\n" in body else body
        else:
            body = s[-3000:]
        out.append({
            "job": name,
            "job_id": jid,
            "file": os.path.basename(f),
            "mtime": datetime.fromtimestamp(os.path.getmtime(f)).isoformat(timespec="seconds"),
            "age_min": int((os.path.getmtime(f)) and (datetime.now().timestamp() - os.path.getmtime(f)) / 60),
            "body": body[:6000],
        })
        if len(out) >= limit:
            break
    return out


def summary() -> Dict[str, Any]:
    jobs = _load_jobs()
    live = [j for j in jobs if _active(j)]
    failing = [j for j in live if _failed(j)]
    soon = sorted([j for j in live if j.get("next_run_at")], key=lambda j: j["next_run_at"])[:6]
    return {
        "total_jobs": len(jobs),
        "live": len(live),
        "failing": len(failing),
        "failing_names": [j.get("name") for j in failing[:8]],
        "next_up": [{"name": j.get("name"), "next_run_at": j.get("next_run_at")} for j in soon],
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def report_text(job_id: str, filename: Optional[str] = None) -> Optional[str]:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", job_id):
        return None
    d = os.path.join(OUTPUT_DIR, job_id)
    if filename:
        if filename != os.path.basename(filename) or not filename.endswith((".md", ".txt")):
            return None
        f = os.path.join(d, filename)
        if os.path.isfile(f):
            return open(f, errors="ignore").read()
        return None
    files = sorted(glob.glob(os.path.join(d, "*.md")), key=os.path.getmtime, reverse=True)
    if not files:
        return None
    return open(files[0], errors="ignore").read()