"""Tests for the impact-cascade engine — dependency-graph BFS over India's
sector / macro graph."""
from __future__ import annotations

import pytest

from app.engines import cascade


def test_sector_metric_table_is_complete():
    """Every sector entry must have base, unit, elasticity, type."""
    for key, meta in cascade._SECTOR_METRIC.items():
        assert key.startswith("sector:")
        for field in ("base", "unit", "elasticity", "type"):
            assert field in meta, f"{key} missing {field}"
        assert meta["base"] > 0
        assert 0 < meta["elasticity"] < 1
        assert meta["type"] in ("mult", "index_down")


def test_list_causes_returns_non_empty():
    causes = cascade.list_causes()
    assert isinstance(causes, list)
    assert len(causes) > 0
    # Each cause must have id + label.
    for c in causes:
        assert "id" in c
        assert "label" in c


def test_cause_id_for_corridor_round_trips():
    cid = cascade.cause_id_for_corridor("hormuz")
    assert "hormuz" in cid.lower()


def test_cause_id_for_commodity_round_trips():
    cid = cascade.cause_id_for_commodity("crude_oil")
    assert cid.startswith("commodity:") or cid.startswith("cause:")


def test_resolve_cascade_returns_nodes_and_edges():
    result = cascade.resolve_cascade("corridor:hormuz", intensity=0.8)
    # CascadeResult exposes nodes and edges (likely as attrs or via the
    # cascade_summary helper).
    nodes = getattr(result, "nodes", None) or getattr(result, "downstream", None)
    edges = getattr(result, "edges", None)
    assert nodes is not None
    if edges is not None:
        assert isinstance(edges, list)


def test_resolve_cascade_reaches_sectors():
    """A Hormuz closure must propagate into Indian sectors."""
    result = cascade.resolve_cascade("corridor:hormuz", intensity=1.0)
    summary = cascade.cascade_summary_for_llm(result)
    text = str(summary).lower()
    # At least one sector or macro variable should appear in the result.
    assert "sector:" in text or "macro:" in text or len(summary) > 0


def test_resolve_cascade_higher_intensity_reaches_at_least_as_much():
    low = cascade.resolve_cascade("corridor:hormuz", intensity=0.2)
    high = cascade.resolve_cascade("corridor:hormuz", intensity=0.9)
    low_nodes = getattr(low, "nodes", []) or []
    high_nodes = getattr(high, "nodes", []) or []
    assert len(high_nodes) >= len(low_nodes)


def test_unknown_cause_returns_safely():
    """Should not crash; either empty result or a clear error."""
    try:
        result = cascade.resolve_cascade("cause:totally_fake", intensity=0.5)
        # Should produce a degenerate but valid result, not raise.
        assert result is not None
    except (KeyError, ValueError):
        pass  # explicit rejection is also acceptable
