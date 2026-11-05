"""Email-code routes and authentication middleware for the Command Center."""
import asyncio
import json
import os
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse

from dashboard.backend.services import auth_gate

auth_router = APIRouter()
FRONTEND_DIST = os.environ.get("DASHBOARD_FRONTEND_DIST", "/home/lurkr/ai-platform/dashboard/frontend/dist")
LOGIN_CANDIDATES = (
    Path(FRONTEND_DIST) / "login.html",
    Path(__file__).resolve().parents[2] / "frontend" / "public" / "login.html",
)
PUBLIC_PATHS = {"/login", "/health", "/vite.svg", "/logo-icon-48.png"}
PUBLIC_PREFIXES = ("/api/auth/", "/assets/")


def _is_public(path: str) -> bool:
    return path in PUBLIC_PATHS or any(path.startswith(prefix) for prefix in PUBLIC_PREFIXES)


async def _json_object(request: Request) -> dict | None:
    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return body if isinstance(body, dict) else None


@auth_router.post("/api/auth/request")
async def auth_request(request: Request):
    body = await _json_object(request)
    if body is None:
        return JSONResponse({"ok": False, "detail": "Invalid request body."}, status_code=400)
    email = body.get("email", "")
    if not isinstance(email, str):
        return JSONResponse({"ok": False, "detail": "Enter a valid email address."}, status_code=400)
    await asyncio.to_thread(auth_gate.send_code, email)
    # Identical response for allowlisted, unknown, and rate-limited addresses.
    return {
        "ok": True,
        "message": "If your email is allowlisted, a code is on its way. Check your inbox (and spam).",
    }


@auth_router.post("/api/auth/verify")
async def auth_verify(request: Request):
    body = await _json_object(request)
    if body is None:
        return JSONResponse({"ok": False, "detail": "Invalid request body."}, status_code=400)
    email = body.get("email", "")
    code = body.get("code", "")
    if not isinstance(email, str) or not isinstance(code, str):
        return JSONResponse({"ok": False, "detail": "Invalid or expired code."}, status_code=400)
    requester = request.client.host if request.client else None
    session = await asyncio.to_thread(auth_gate.verify_code, email, code, requester)
    if not session:
        return JSONResponse({"ok": False, "detail": "Invalid or expired code."}, status_code=401)
    response = JSONResponse({"ok": True})
    response.set_cookie(
        auth_gate.SESS_COOKIE, session,
        max_age=auth_gate.SESSION_TTL_S, httponly=True, samesite="lax", secure=True,
    )
    return response


@auth_router.api_route("/api/auth/logout", methods=["GET", "POST"])
async def auth_logout(request: Request):
    await asyncio.to_thread(auth_gate.end_session, request.cookies.get(auth_gate.SESS_COOKIE))
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(auth_gate.SESS_COOKIE, secure=True, httponly=True, samesite="lax")
    return response


@auth_router.get("/api/auth/check")
async def auth_check(request: Request):
    valid = auth_gate.session_valid(request.cookies.get(auth_gate.SESS_COOKIE))
    return {"authenticated": valid}


@auth_router.get("/login")
async def login_page():
    for path in LOGIN_CANDIDATES:
        try:
            return HTMLResponse(path.read_text())
        except OSError:
            continue
    return HTMLResponse("Command Center login is temporarily unavailable.", status_code=503)


class AuthGateMiddleware:
    """Require a valid session for private HTTP routes and WebSocket handshakes."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "/")

        if scope["type"] == "http":
            original_send = send

            async def send_secure(message):
                if message["type"] == "http.response.start":
                    headers = [
                        (key, value) for key, value in message.get("headers", [])
                        if key.lower() not in (b"cache-control", b"x-frame-options", b"x-content-type-options", b"referrer-policy")
                    ]
                    if path.startswith(("/api/", "/assets/")) or path in ("/", "/index.html", "/login"):
                        headers.append((b"cache-control", b"no-store"))
                    headers.extend([
                        (b"x-frame-options", b"DENY"),
                        (b"x-content-type-options", b"nosniff"),
                        (b"referrer-policy", b"no-referrer"),
                    ])
                    message = {**message, "headers": headers}
                await original_send(message)

            send = send_secure

        if _is_public(path):
            await self.app(scope, receive, send)
            return

        session = None
        for name, value in scope.get("headers", []):
            if name.lower() == b"cookie":
                for part in value.decode("latin-1").split(";"):
                    key, _, val = part.strip().partition("=")
                    if key == auth_gate.SESS_COOKIE:
                        session = val
                        break
                break

        if not auth_gate.session_valid(session):
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1008})
                return
            if path.startswith("/api/"):
                response = JSONResponse({"detail": "Not authenticated"}, status_code=401)
            else:
                response = RedirectResponse("/login", status_code=303)
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)
