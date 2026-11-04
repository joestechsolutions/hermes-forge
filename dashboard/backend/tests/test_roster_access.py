"""Authentication and roster privacy tests using isolated, non-secret test sessions."""
import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    from dashboard.backend.services import auth_gate
    monkeypatch.setattr(auth_gate, "STATE_DIR", str(tmp_path))
    monkeypatch.setattr(auth_gate, "CODES_FILE", str(tmp_path / "auth.json"))
    monkeypatch.setattr(auth_gate, "send_code", lambda email: True)
    from dashboard.backend.main import app
    return TestClient(app, base_url="https://testserver")


def test_unauthenticated_roster_read_is_denied(client):
    assert client.get("/api/v1/agents").status_code == 401


def test_isolated_email_code_session_allows_ledger(client, monkeypatch, tmp_path):
    from dashboard.backend.services import auth_gate
    from dashboard.backend.services import agent_roster
    profile = tmp_path / "profiles" / "ledger"
    profile.mkdir(parents=True)
    (profile / "profile.yaml").write_text("display_name: Ledger\ndescription: Revenue analyst\n")
    monkeypatch.setattr(agent_roster.os, "environ", {"HERMES_HOME": str(tmp_path)})
    # Directly write a hashed test code; never touch or read production auth state.
    email = "joe@joestechsolutions.com"
    code = "123456"
    hashed_email = auth_gate._hash(email)
    hashed_code = auth_gate._hash(code + ":" + hashed_email)
    Path(auth_gate.CODES_FILE).write_text(json.dumps({
        hashed_code: {"email": hashed_email, "exp": time.time() + 600, "tries": 0}
    }))
    response = client.post("/api/auth/verify", json={"email": email, "code": code})
    assert response.status_code == 200
    cookie = response.headers.get("set-cookie", "")
    assert "HttpOnly" in cookie and "Secure" in cookie
    assert "samesite=lax" in cookie.lower()
    response = client.get("/api/v1/agents")
    assert response.status_code == 200
    assert response.json()["agents"][0]["name"] == "Ledger"
    # Single use: the same code cannot be replayed.
    assert client.post("/api/auth/verify", json={"email": email, "code": code}).status_code == 401


def test_unknown_email_cannot_sign_in(client):
    assert client.post("/api/auth/verify", json={"email": "not-allowed@example.com", "code": "123456"}).status_code == 401
