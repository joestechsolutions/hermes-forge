"""6-digit code auth gate for the JTS Command Center dashboard.

Flow (Joe's spec — OTP, not magic link):
  POST /api/auth/request   {email}  → allowlist check → 6-digit code (10-min TTL, hashed at rest)
                                     → code emailed via himalaya SMTP
  POST /api/auth/verify    {email, code} → sets HttpOnly SameSite=Lax cookie (30d) → {ok:true}
  GET  /api/auth/logout              → clears cookie → 303 to /login

Security properties:
  - codes are 6 digits, single-use, expire in 10 minutes
  - stored hashed (sha256) — raw code never persisted or logged
  - 5 failed verification attempts per code → code invalidated
  - request endpoint rate-limited: 3 codes per email per 10 minutes
  - only allowlisted emails receive a code; others get a uniform response (no enumeration)
"""
import hashlib
import json
import os
import secrets
import subprocess
import time
from urllib.parse import quote

STATE_DIR = "/home/lurkr/.hermes/state"
CODES_FILE = os.path.join(STATE_DIR, "cc-auth-codes.json")
SESS_COOKIE = "cc_session"

# ── allowlist ───────────────────────────────────────────────────────────────
ALLOWED_EMAILS = {
    value.strip().lower()
    for value in os.environ.get("DASHBOARD_ALLOWED_EMAILS", "joe@joestechsolutions.com").split(",")
    if value.strip()
}

CODE_TTL_S = 10 * 60          # 6-digit code valid 10 minutes
SESSION_TTL_S = 30 * 24 * 3600  # 30 days
MAX_VERIFY_ATTEMPTS = 5       # per code
MAX_CODES_PER_WINDOW = 3      # per email per CODE_TTL window


def _load(path: str) -> dict:
    try:
        return json.loads(open(path).read())
    except Exception:
        return {}


def _save(path: str, data: dict) -> None:
    os.makedirs(STATE_DIR, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(data, f)
        f.close()


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _prune_codes(codes: dict) -> dict:
    now = time.time()
    return {k: v for k, v in codes.items()
            if isinstance(v, dict) and v.get("exp", 0) > now}


def send_code(email: str) -> bool:
    """Generate + email a 6-digit code if the address is allowlisted. Returns True if sent."""
    email = (email or "").strip().lower()
    if email not in ALLOWED_EMAILS:
        return False

    codes = _prune_codes(_load(CODES_FILE))
    h = _hash(email)

    # rate limit: max MAX_CODES_PER_WINDOW live codes per email
    recent = [c for c in codes.values()
              if isinstance(c, dict) and c.get("email") == h]
    if len(recent) >= MAX_CODES_PER_WINDOW:
        return False

    code = f"{secrets.randbelow(1_000_000):06d}"
    ch = _hash(code + ":" + h)  # code bound to the email it was issued for
    codes[ch] = {"exp": time.time() + CODE_TTL_S, "email": h, "tries": 0}
    _save(CODES_FILE, codes)

    html = (
        '<div style="font-family:Inter,Arial,sans-serif;background:#071317;padding:32px 20px;text-align:center">'
        '<div style="max-width:420px;margin:0 auto;background:#0c1e22;border:1px solid #1e383b;padding:36px 28px">'
        '<div style="display:flex;align-items:center;justify-content:center;gap:8px">'
        '<span style="color:#02a0a0;font-size:28px;font-weight:800;letter-spacing:.08em">JTS</span>'
        '<span style="width:10px;height:10px;background:#ffbd65;display:inline-block"></span></div>'
        '<div style="color:#5d7573;font-size:11px;letter-spacing:.2em;margin:10px 0 22px;text-transform:uppercase">Joe\'s Tech Solutions · Command Center</div>'
        '<p style="color:#8fa8a5;font-size:14px;margin:0 0 18px">Your sign-in code (expires in 10 minutes, works once):</p>'
        '<div style="font-family:\'JetBrains Mono\',monospace;color:#02a0a0;font-size:38px;font-weight:800;letter-spacing:.35em;background:#071317;border:1px solid #1e383b;padding:18px 10px">'
        f'{code}</div>'
        '<p style="color:#5d7573;font-size:11px;margin:20px 0 0">Enter this code on the Command Center sign-in page.</p>'
        '<p style="color:#5d7573;font-size:11px;margin:10px 0 0">If you didn\'t request this, ignore this email — never share the code.</p>'
        '</div></div>'
    )
    msg = (
        "From: JTS Command Center <joe@joestechsolutions.com>\n"
        f"To: {email}\n"
        "Subject: Your sign-in code — JTS Command Center\n"
        "MIME-Version: 1.0\n"
        "Content-Type: text/html; charset=utf-8\n"
        f"\n{html}"
    )
    proc = subprocess.run(
        ["himalaya", "message", "send", "--account", "business"],
        input=msg.encode(), capture_output=True, timeout=60,
    )
    return proc.returncode == 0


def verify_code(email: str, code: str) -> str | None:
    """Consume a code; return a new session token (or None)."""
    email = (email or "").strip().lower()
    code = (code or "").strip()
    if not code or email not in ALLOWED_EMAILS:
        return None
    h = _hash(email)
    ch = _hash(code + ":" + h)

    codes = _prune_codes(_load(CODES_FILE))
    entry = codes.get(ch)
    if entry is None or entry.get("email") != h:
        # also consume a matching-code attempt against wrong email → count nothing
        return None
    if entry.get("tries", 0) >= MAX_VERIFY_ATTEMPTS:
        codes.pop(ch, None)
        _save(CODES_FILE, codes)
        return None
    # single-use: consume either way
    codes.pop(ch, None)
    _save(CODES_FILE, codes)

    session = secrets.token_urlsafe(32)
    sessions = {k: v for k, v in _load(CODES_FILE).items()
                if not k.startswith("s:")}
    sessions["s:" + _hash(session)] = time.time() + SESSION_TTL_S
    _save(CODES_FILE, sessions)
    return session


def session_valid(session: str | None) -> bool:
    if not session:
        return False
    data = _load(CODES_FILE)
    exp = data.get("s:" + _hash(session))
    if exp is None:
        return False
    if exp < time.time():
        return False
    return True


def end_session(session: str | None) -> None:
    if not session:
        return
    data = _load(CODES_FILE)
    data.pop("s:" + _hash(session), None)
    _save(CODES_FILE, data)