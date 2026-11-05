"""Six-digit email-code authentication for the JTS Command Center.

Codes are hashed, bound to an email, single-use, and expire in ten minutes. Failed
verification is limited per email and per client IP. Sessions are independent,
expire after 30 days, and coexist with pending codes. All writes are locked and
atomic so a new login cannot erase another device or a concurrent request.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import secrets
import subprocess
import tempfile
import time
from collections.abc import Callable
from typing import Any

STATE_DIR = "/home/lurkr/.hermes/state"
CODES_FILE = os.path.join(STATE_DIR, "cc-auth-codes.json")
SESS_COOKIE = "cc_session"

ALLOWED_EMAILS = {
    value.strip().lower()
    for value in os.environ.get("DASHBOARD_ALLOWED_EMAILS", "joe@joestechsolutions.com").split(",")
    if value.strip()
}
CODE_TTL_S = 10 * 60
SESSION_TTL_S = 30 * 24 * 3600
MAX_VERIFY_ATTEMPTS = 5
MAX_VERIFY_IP_ATTEMPTS = 30
MAX_CODES_PER_WINDOW = 3


def _load(path: str) -> dict[str, Any]:
    try:
        with open(path) as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        # Corrupt state fails closed: no code or session is accepted.
        return {}


def _save(path: str, data: dict[str, Any]) -> None:
    directory = os.path.dirname(path)
    os.makedirs(directory, mode=0o700, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".cc-auth-", dir=directory)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as handle:
            json.dump(data, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _prune_state(state: dict[str, Any]) -> dict[str, Any]:
    now = time.time()
    result = {}
    for key, value in state.items():
        # Migrate legacy bare-float sessions without logging out existing devices.
        if key.startswith("s:") and isinstance(value, (int, float)):
            value = {"exp": value}
        if isinstance(value, dict) and value.get("exp", 0) > now:
            result[key] = value
    return result


def _update(mutator: Callable[[dict[str, Any]], Any]) -> Any:
    """Serialize a read-modify-write across concurrent dashboard requests."""
    lock_path = CODES_FILE + ".lock"
    os.makedirs(os.path.dirname(CODES_FILE), mode=0o700, exist_ok=True)
    with open(lock_path, "a+") as lock:
        os.fchmod(lock.fileno(), 0o600)
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        state = _prune_state(_load(CODES_FILE))
        result = mutator(state)
        _save(CODES_FILE, state)
        return result


def _code_keys(state: dict[str, Any], email_hash: str) -> list[str]:
    return [
        key for key, value in state.items()
        if not key.startswith(("s:", "f:", "v:")) and isinstance(value, dict) and value.get("email") == email_hash
    ]


def send_code(email: str) -> bool:
    """Generate and email a code only for an allowlisted address."""
    email = (email or "").strip().lower()
    if email not in ALLOWED_EMAILS:
        return False
    email_hash = _hash(email)
    code = f"{secrets.randbelow(1_000_000):06d}"
    code_hash = _hash(code + ":" + email_hash)

    def add_code(state: dict[str, Any]) -> bool:
        if len(_code_keys(state, email_hash)) >= MAX_CODES_PER_WINDOW:
            return False
        state[code_hash] = {"exp": time.time() + CODE_TTL_S, "email": email_hash, "tries": 0}
        return True

    if not _update(add_code):
        return False

    html = (
        '<div style="font-family:Inter,Arial,sans-serif;background:#071317;padding:32px 20px;text-align:center">'
        '<div style="max-width:420px;margin:0 auto;background:#0c1e22;border:1px solid #1e383b;padding:36px 28px;border-radius:20px">'
        '<div style="display:flex;align-items:center;justify-content:center;gap:8px">'
        '<span style="color:#02a0a0;font-size:28px;font-weight:800;letter-spacing:.08em">JTS</span>'
        '<span style="width:10px;height:10px;background:#ffbd65;display:inline-block"></span></div>'
        '<div style="color:#8fa8a5;font-size:11px;letter-spacing:.2em;margin:10px 0 22px;text-transform:uppercase">Joe\'s Tech Solutions · Command Center</div>'
        '<p style="color:#b7d2cd;font-size:14px;margin:0 0 18px">Your sign-in code (expires in 10 minutes, works once):</p>'
        '<div style="font-family:\'JetBrains Mono\',monospace;color:#4ecdc4;font-size:38px;font-weight:800;letter-spacing:.35em;background:#071317;border:1px solid #1e383b;padding:18px 10px;border-radius:12px">'
        f'{code}</div>'
        '<p style="color:#8fa8a5;font-size:11px;margin:20px 0 0">Enter this code on the Command Center sign-in page.</p>'
        '<p style="color:#8fa8a5;font-size:11px;margin:10px 0 0">If you didn\'t request this, ignore this email — never share the code.</p>'
        '</div></div>'
    )
    message = (
        "From: JTS Command Center <joe@joestechsolutions.com>\n"
        f"To: {email}\n"
        "Subject: Your sign-in code — JTS Command Center\n"
        "MIME-Version: 1.0\n"
        "Content-Type: text/html; charset=utf-8\n"
        f"\n{html}"
    )
    try:
        proc = subprocess.run(
            ["himalaya", "message", "send", "--account", "business"],
            input=message.encode(), capture_output=True, timeout=60,
        )
        sent = proc.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        sent = False
    if not sent:
        _update(lambda state: state.pop(code_hash, None))
    return sent


def verify_code(email: str, code: str, requester: str | None = None) -> str | None:
    """Consume a valid code and add an independent session, or return None."""
    email = (email or "").strip().lower()
    code = (code or "").strip()
    email_hash = _hash(email)
    failure_key = "f:" + email_hash
    ip_key = "v:" + _hash(requester) if requester else None

    def consume(state: dict[str, Any]) -> str | None:
        if ip_key:
            ip_entry = state.get(ip_key, {"count": 0, "exp": time.time() + CODE_TTL_S})
            if ip_entry.get("count", 0) >= MAX_VERIFY_IP_ATTEMPTS:
                return None

        def record_ip_failure() -> None:
            if not ip_key:
                return
            entry = state.get(ip_key, {"count": 0, "exp": time.time() + CODE_TTL_S})
            entry["count"] = entry.get("count", 0) + 1
            state[ip_key] = entry

        if email not in ALLOWED_EMAILS or len(code) != 6 or not code.isdigit():
            record_ip_failure()
            return None
        failure = state.get(failure_key, {"count": 0, "exp": time.time() + CODE_TTL_S})
        if failure.get("count", 0) >= MAX_VERIFY_ATTEMPTS:
            return None

        code_hash = _hash(code + ":" + email_hash)
        entry = state.get(code_hash)
        if not isinstance(entry, dict) or entry.get("email") != email_hash:
            failure["count"] = failure.get("count", 0) + 1
            state[failure_key] = failure
            record_ip_failure()
            if failure["count"] >= MAX_VERIFY_ATTEMPTS:
                for key in _code_keys(state, email_hash):
                    state.pop(key, None)
            return None

        # Valid code: invalidate all outstanding codes for this email, retain sessions.
        for key in _code_keys(state, email_hash):
            state.pop(key, None)
        state.pop(failure_key, None)
        if ip_key:
            state.pop(ip_key, None)
        session = secrets.token_urlsafe(32)
        state["s:" + _hash(session)] = {"exp": time.time() + SESSION_TTL_S}
        return session

    return _update(consume)


def session_valid(session: str | None) -> bool:
    if not session:
        return False
    data = _prune_state(_load(CODES_FILE))
    entry = data.get("s:" + _hash(session))
    return isinstance(entry, dict) and entry.get("exp", 0) > time.time()


def end_session(session: str | None) -> None:
    if not session:
        return
    session_key = "s:" + _hash(session)
    _update(lambda state: state.pop(session_key, None))
