"""Shared pytest fixtures."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def app():
    from app.main import app as fastapi_app
    return fastapi_app


@pytest.fixture()
def client(app) -> TestClient:
    """Fresh TestClient per-test so the lifespan hook runs once per session
    but each test sees a clean request context."""
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def disable_persistence(monkeypatch):
    """Stub the persistence module so tests that hit POST endpoints don't
    accidentally bloat backend/data/state.db across runs."""
    from app import persistence
    monkeypatch.setattr(persistence, "save_override", lambda *a, **k: True)
    monkeypatch.setattr(persistence, "log_scenario_run", lambda *a, **k: 1)
    monkeypatch.setattr(persistence, "list_scenario_runs", lambda **k: [])
    monkeypatch.setattr(persistence, "get_scenario_run", lambda *a, **k: None)
