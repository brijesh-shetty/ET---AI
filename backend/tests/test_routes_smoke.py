"""Smoke tests for the main API endpoints — verify shape, not exact values."""
from __future__ import annotations

import pytest


def test_healthz(client):
    r = client.get("/api/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "asOf" in body


def test_scenarios_catalogue(client):
    r = client.get("/api/scenarios")
    assert r.status_code == 200
    items = r.json()
    assert isinstance(items, list)
    assert len(items) >= 7  # PS2 has 7 named scenarios


def test_run_scenario_returns_full_envelope(client):
    r = client.post(
        "/api/scenarios/hormuz_partial_closure/run",
        json={"intensity": 0.5, "duration_days": 21},
    )
    assert r.status_code == 200
    body = r.json()
    for key in ("scenarioId", "request", "baseline", "projected", "timeline", "recommendations"):
        assert key in body, f"missing key {key}"
    # Per-scenario timeline fields (PS-required cascading impacts)
    sample = body["timeline"][0]
    for field in ("brentUsd", "refineryRunRatePct", "dieselPriceInr", "powerStressIndex", "gdpGrowthPct"):
        assert field in sample, f"missing timeline field {field}"


def test_run_unknown_scenario_404s(client):
    r = client.post("/api/scenarios/nope/run", json={"intensity": 0.5, "duration_days": 30})
    assert r.status_code == 404


def test_compound_scenarios(client):
    r = client.post(
        "/api/scenarios/compound",
        json={
            "scenarios": [
                {"name": "hormuz_partial_closure", "intensity": 0.5, "duration_days": 21},
                {"name": "australia_coking_coal", "intensity": 0.5, "duration_days": 30},
            ]
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["kind"] == "compound"
    assert len(body["constituents"]) == 2
    assert len(body["breakdown"]) == 2
    assert "timeline" in body and len(body["timeline"]) > 0
    assert "notes" in body and len(body["notes"]) > 0


def test_compound_rejects_empty_list(client):
    r = client.post("/api/scenarios/compound", json={"scenarios": []})
    assert r.status_code == 400


def test_compound_rejects_too_many(client):
    r = client.post(
        "/api/scenarios/compound",
        json={"scenarios": [{"name": "hormuz_partial_closure"}] * 5},
    )
    assert r.status_code == 400


def test_digital_twin_state_has_vessels(client):
    r = client.get("/api/digital-twin/state")
    assert r.status_code == 200
    body = r.json()
    assert "vesselPositions" in body
    assert isinstance(body["vesselPositions"], list)
    assert len(body["vesselPositions"]) > 0  # fixture has 60+
    v = body["vesselPositions"][0]
    for k in ("mmsi", "name", "lat", "lon", "cargo", "flag", "corridor", "anomaly"):
        assert k in v, f"vessel missing field {k}"


def test_digital_twin_has_pipelines(client):
    r = client.get("/api/digital-twin/state")
    body = r.json()
    assert "oilPipelines" in body and len(body["oilPipelines"]) > 0
    assert "gasPipelines" in body and len(body["gasPipelines"]) > 0
    p = body["oilPipelines"][0]
    assert "polyline" in p and len(p["polyline"]) > 0


def test_baselines_endpoint(client):
    r = client.get("/api/baselines")
    assert r.status_code == 200
    body = r.json()
    assert "live" in body
    assert "operator_overridable" in body


def test_baselines_override_validates_range(client, disable_persistence):
    r = client.post("/api/baselines/override", json={"spr_cover_days": 1000.0})
    assert r.status_code == 200
    body = r.json()
    assert "spr_cover_days" in body["errors"]
    assert "out of range" in body["errors"]["spr_cover_days"]


def test_scores_returns_list(client):
    r = client.get("/api/scores")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)


def test_spr_plan_endpoint(client):
    r = client.get("/api/spr/plan")
    assert r.status_code == 200
    body = r.json()
    assert "coverDays" in body
    assert "releaseSchedule" in body


def test_scenario_run_endpoint(client, disable_persistence):
    """Verify the audit-log endpoints exist (return at least an empty list)."""
    r = client.get("/api/scenario-runs?limit=5")
    assert r.status_code == 200
    body = r.json()
    assert "runs" in body


@pytest.mark.parametrize("name", ["hormuz_partial_closure", "australia_coking_coal", "kazakhstan_uranium_disruption"])
def test_per_scenario_refinery_differentiation(client, name):
    """The crux of PS module 2 fidelity: refinery run rate must differ per
    scenario, not just by intensity. Hormuz cuts hard; uranium leaves it alone."""
    r = client.post(f"/api/scenarios/{name}/run", json={"intensity": 1.0, "duration_days": 30})
    body = r.json()
    final_run_rate = body["timeline"][-1]["refineryRunRatePct"]
    if name == "hormuz_partial_closure":
        assert final_run_rate < 90.0, "Hormuz must significantly cut refinery run rate"
    else:
        # Non-oil scenarios should leave the refinery at ~100%.
        assert final_run_rate >= 99.0, f"{name} should not deflect refinery run rate"
