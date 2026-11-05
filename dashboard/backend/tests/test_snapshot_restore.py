"""Regression tests for issue #5: snapshot restore name selection."""
import asyncio
from pathlib import Path

import pytest
from fastapi import HTTPException

from dashboard.backend.api import routes


class FakeStateManager:
    def __init__(self, snapshots):
        self.snapshots = snapshots
        self.loaded = []
        self.applied = []

    def list_snapshots(self):
        return self.snapshots

    def load_snapshot(self, path):
        self.loaded.append(path)
        return {"metadata": {"name": path.stem}}

    def apply_snapshot(self, snapshot):
        self.applied.append(snapshot["metadata"]["name"])
        return {"errors": [], "restored_configs": [], "restored_services": []}


def snapshot(tmp_path: Path, name: str):
    path = tmp_path / f"{name}.json"
    path.write_text("{}")
    return {"name": name, "file": str(path), "timestamp": "2026-11-05T00:00:00Z"}


def install_fake(monkeypatch, snapshots):
    manager = FakeStateManager(snapshots)
    monkeypatch.setattr(routes, "StateManager", lambda _home: manager)
    return manager


def test_exact_match_wins_regardless_of_list_order(monkeypatch, tmp_path):
    """The prefix-listed snapshot must not win over the exact name."""
    manager = install_fake(monkeypatch, [
        snapshot(tmp_path, "pre-install-2"),
        snapshot(tmp_path, "pre-install"),
    ])

    result = asyncio.run(routes.restore_snapshot("pre-install"))

    assert result.status == "ok"
    assert manager.applied == ["pre-install"]


def test_ambiguous_prefix_returns_409_without_restoring(monkeypatch, tmp_path):
    manager = install_fake(monkeypatch, [
        snapshot(tmp_path, "pre-install-2"),
        snapshot(tmp_path, "pre-install-3"),
    ])

    with pytest.raises(HTTPException) as raised:
        asyncio.run(routes.restore_snapshot("pre-install"))

    assert raised.value.status_code == 409
    assert "ambiguous" in raised.value.detail.lower()
    assert "pre-install-2" in raised.value.detail
    assert "pre-install-3" in raised.value.detail
    assert manager.loaded == []
    assert manager.applied == []


def test_unique_prefix_still_restores(monkeypatch, tmp_path):
    manager = install_fake(monkeypatch, [
        snapshot(tmp_path, "weekly-20261105"),
        snapshot(tmp_path, "pre-install"),
    ])

    result = asyncio.run(routes.restore_snapshot("weekly"))

    assert result.status == "ok"
    assert manager.applied == ["weekly-20261105"]


def test_missing_snapshot_returns_404(monkeypatch, tmp_path):
    manager = install_fake(monkeypatch, [snapshot(tmp_path, "weekly-20261105")])

    with pytest.raises(HTTPException) as raised:
        asyncio.run(routes.restore_snapshot("missing"))

    assert raised.value.status_code == 404
    assert manager.loaded == []
    assert manager.applied == []
