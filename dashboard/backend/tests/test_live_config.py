"""Live model configuration must reflect config edits without a dashboard restart."""
import json
from dashboard.backend.services import live_config


def test_current_model_comes_from_config(tmp_path, monkeypatch):
    config = tmp_path / "config.yaml"
    config.write_text("model:\n  default: kimi-k3.1-pro:cloud\n  provider: ollama-launch\n  base_url: https://ollama.com/v1\n")
    monkeypatch.setenv("HERMES_CONFIG", str(config))
    monkeypatch.setattr(live_config.Path, "home", lambda: tmp_path)
    data = live_config.model_snapshot()
    assert data["name"] == "kimi-k3.1-pro:cloud"
    assert data["provider"] == "ollama-launch"
    assert data["models"][0]["role"] == "Primary conversation"
    assert "api_key" not in json.dumps(data).lower()


def test_model_change_is_visible_on_next_read(tmp_path, monkeypatch):
    config = tmp_path / "config.yaml"
    config.write_text("model:\n  default: first-model\n  provider: first-provider\n")
    monkeypatch.setenv("HERMES_CONFIG", str(config))
    monkeypatch.setattr(live_config.Path, "home", lambda: tmp_path)
    assert live_config.model_snapshot()["name"] == "first-model"
    config.write_text("model:\n  default: kimi-k3.1-pro:cloud\n  provider: ollama-launch\n")
    assert live_config.model_snapshot()["name"] == "kimi-k3.1-pro:cloud"
