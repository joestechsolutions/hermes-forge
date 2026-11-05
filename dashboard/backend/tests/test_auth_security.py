"""Security regressions from the independent Command Center review."""
import json
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from dashboard.backend.services import auth_gate

EMAIL = "joe@joestechsolutions.com"


@pytest.fixture
def isolated_auth(monkeypatch, tmp_path):
    monkeypatch.setattr(auth_gate, "STATE_DIR", str(tmp_path))
    monkeypatch.setattr(auth_gate, "CODES_FILE", str(tmp_path / "auth.json"))
    monkeypatch.setattr(auth_gate, "ALLOWED_EMAILS", {EMAIL})
    return auth_gate


def seed_code(auth, email: str, code: str):
    email_hash = auth._hash(email)
    key = auth._hash(code + ":" + email_hash)
    auth._update(lambda state: state.__setitem__(key, {
        "email": email_hash, "exp": auth.time.time() + auth.CODE_TTL_S, "tries": 0,
    }))


def test_five_failures_invalidate_code_without_killing_existing_session(isolated_auth):
    seed_code(isolated_auth, EMAIL, "111111")
    existing = isolated_auth.verify_code(EMAIL, "111111")
    assert existing
    seed_code(isolated_auth, EMAIL, "222222")
    for _ in range(isolated_auth.MAX_VERIFY_ATTEMPTS):
        assert isolated_auth.verify_code(EMAIL, "999999") is None
    assert isolated_auth.verify_code(EMAIL, "222222") is None
    assert isolated_auth.session_valid(existing)
    with open(isolated_auth.CODES_FILE) as handle:
        persisted = handle.read()
    assert "222222" not in persisted
    assert "999999" not in persisted


def test_code_request_and_second_login_preserve_first_device(isolated_auth, monkeypatch):
    seed_code(isolated_auth, EMAIL, "111111")
    first = isolated_auth.verify_code(EMAIL, "111111")
    assert isolated_auth.session_valid(first)

    monkeypatch.setattr(isolated_auth.secrets, "randbelow", lambda _: 42)
    monkeypatch.setattr(isolated_auth.subprocess, "run", lambda *a, **k: MagicMock(returncode=0))
    assert isolated_auth.send_code(EMAIL)
    assert isolated_auth.session_valid(first)
    second = isolated_auth.verify_code(EMAIL, "000042")
    assert second and second != first
    assert isolated_auth.session_valid(first)
    assert isolated_auth.session_valid(second)


def test_verify_ip_limit_and_legacy_session_migration(isolated_auth, monkeypatch):
    legacy = "legacy-session"
    isolated_auth._save(isolated_auth.CODES_FILE, {
        "s:" + isolated_auth._hash(legacy): isolated_auth.time.time() + 1000,
    })
    assert isolated_auth.session_valid(legacy)

    monkeypatch.setattr(isolated_auth, "MAX_VERIFY_IP_ATTEMPTS", 2)
    seed_code(isolated_auth, EMAIL, "333333")
    assert isolated_auth.verify_code(EMAIL, "000001", "192.0.2.1") is None
    assert isolated_auth.verify_code(EMAIL, "000002", "192.0.2.1") is None
    assert isolated_auth.verify_code(EMAIL, "333333", "192.0.2.1") is None
    assert isolated_auth.verify_code(EMAIL, "333333", "192.0.2.2")
    assert isolated_auth.session_valid(legacy)


def test_auth_routes_reject_malformed_json_and_ws_without_traceback(isolated_auth, monkeypatch):
    from dashboard.backend.main import app
    client = TestClient(app, base_url="https://testserver")
    malformed = client.post("/api/auth/request", content="{", headers={"content-type": "application/json"})
    assert malformed.status_code == 400
    with pytest.raises(WebSocketDisconnect) as rejected:
        with client.websocket_connect("/ws/metrics"):
            pass
    assert rejected.value.code == 1008


def test_unknown_and_known_email_requests_have_identical_response(isolated_auth, monkeypatch):
    from dashboard.backend.main import app
    monkeypatch.setattr(auth_gate, "send_code", lambda email: False)
    client = TestClient(app, base_url="https://testserver")
    known = client.post("/api/auth/request", json={"email": EMAIL})
    unknown = client.post("/api/auth/request", json={"email": "unknown@example.com"})
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()
    assert known.headers["cache-control"] == "no-store"
