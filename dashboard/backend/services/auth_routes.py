"""6-digit code auth routes + middleware for the JTS Command Center dashboard."""
import os
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse

from dashboard.backend.services import auth_gate

auth_router = APIRouter()

LOGIN_PAGE_PATH = "/home/lurkr/ai-platform/dashboard/frontend/dist/login.html"

# paths that never require a session
PUBLIC_PATHS = {"/login", "/health", "/vite.svg", "/logo-icon-48.png"}
PUBLIC_PREFIXES = ("/api/auth/", "/assets/")


def _is_public(path: str) -> bool:
    return path in PUBLIC_PATHS or any(path.startswith(p) for p in PUBLIC_PREFIXES)


@auth_router.post("/api/auth/request")
async def auth_request(request: Request):
    body = await request.json()
    email = (body or {}).get("email", "")
    sent = auth_gate.send_code(email)
    # uniform response either way (no email enumeration)
    if sent:
        return {"ok": True, "message": "✓ Code sent. Check your inbox — it expires in 10 minutes."}
    return {"ok": True, "message": "If your email is allowlisted, a code is on its way. Check your inbox (and spam)."}


@auth_router.post("/api/auth/verify")
async def auth_verify(request: Request):
    body = await request.json()
    email = (body or {}).get("email", "")
    code = (body or {}).get("code", "")
    session = auth_gate.verify_code(email, code)
    if not session:
        return JSONResponse(
            {"ok": False, "detail": "Invalid or expired code."},
            status_code=401,
        )
    resp = JSONResponse({"ok": True})
    resp.set_cookie(
        auth_gate.SESS_COOKIE, session,
        max_age=auth_gate.SESSION_TTL_S, httponly=True, samesite="lax", secure=True,
    )
    return resp


@auth_router.get("/api/auth/logout")
async def auth_logout(request: Request):
    auth_gate.end_session(request.cookies.get(auth_gate.SESS_COOKIE))
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie(auth_gate.SESS_COOKIE)
    return resp


@auth_router.get("/api/auth/check")
async def auth_check(request: Request):
    valid = auth_gate.session_valid(request.cookies.get(auth_gate.SESS_COOKIE))
    return {"authenticated": valid}


@auth_router.get("/login")
async def login_page():
    if os.path.exists(LOGIN_PAGE_PATH):
        with open(LOGIN_PAGE_PATH) as f:
            return HTMLResponse(f.read())
    return HTMLResponse(_fallback_login_html())


def _fallback_login_html() -> str:
    return """<!DOCTYPE html><html><head><meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1.0'>
<title>Sign in — JTS Command Center</title></head>
<body style='background:#071317;color:#d9ece9;font-family:Inter,Arial,sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0'>
<div style='text-align:center;max-width:340px;padding:1rem'>
<div style='color:#02a0a0;font-size:2rem;font-weight:800;letter-spacing:.15em'>JTS</div>
<p style='color:#8fa8a5'>Enter your email to receive a 6-digit sign-in code.</p>
<form onsubmit="var b=document.getElementById('b');b.disabled=true;b.textContent='SENDING…';fetch('/api/auth/request',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:document.getElementById('e').value})}).then(()=>{document.getElementById('msg').textContent='Code sent — check your inbox.';b.textContent='SENT';});return false">
<input id='e' type='email' required placeholder='you@yourdomain.com' style='width:100%;padding:10px;background:#071317;border:1px solid #1e383b;color:#d9ece9;box-sizing:border-box'>
<button id='b' style='width:100%;margin-top:10px;padding:10px;background:#02a0a0;color:#04110f;border:0;font-weight:700;cursor:pointer'>SEND CODE</button>
</form>
<p id='msg' style='color:#3ddc84;font-size:12px'></p>
</div></body></html>"""


class AuthGateMiddleware:
    """ASGI middleware: require a valid session cookie for everything except public paths."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            path = scope.get("path", "/")
            if not _is_public(path):
                # pull cookie
                session = None
                for name, value in scope.get("headers", []):
                    if name == b"cookie":
                        for part in value.decode("latin-1").split(";"):
                            k, _, v = part.strip().partition("=")
                            if k == auth_gate.SESS_COOKIE:
                                session = v
                                break
                        break
                if not auth_gate.session_valid(session):
                    if scope["type"] == "websocket":
                        # reject the handshake
                        send_403 = {
                            "type": "http.response.start",
                            "status": 403,
                            "headers": [(b"content-type", b"text/plain")],
                        }
                        await send(send_403)
                        await send({"type": "http.response.body", "body": b"Forbidden"})
                        return
                    # SPA routes → login page; API routes → 401 JSON
                    if path.startswith("/api/"):
                        resp = JSONResponse({"detail": "Not authenticated"}, status_code=401)
                    else:
                        resp = RedirectResponse("/login", status_code=303)
                    await resp(scope, receive, send)
                    return
        path = scope.get("path", "")
        if scope["type"] == "http" and (path.startswith(("/api/", "/assets/")) or path in ("/", "/index.html", "/login")):
            async def send_no_cache(message):
                if message["type"] == "http.response.start":
                    headers = [(k, v) for k, v in message.get("headers", []) if k.lower() != b"cache-control"]
                    headers.append((b"cache-control", b"no-store"))
                    message = {**message, "headers": headers}
                await send(message)
            await self.app(scope, receive, send_no_cache)
            return
        await self.app(scope, receive, send)
