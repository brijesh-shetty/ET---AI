"""Tests for the Strategic Petroleum Reserve linear program."""
from __future__ import annotations

import pytest

from app.engines.spr_lp import SPRConfig, baseline_no_action_plan, solve_spr_plan


def make_config(horizon: int = 14, gap: float = 500.0, reserve: float = 39.0) -> SPRConfig:
    return SPRConfig(
        starting_reserve_mmb=reserve,
        max_daily_drawdown_kbpd=600.0,
        max_daily_replenish_kbpd=200.0,
        daily_consumption_kbpd=5100.0,
        supply_gap_curve=[gap] * horizon,
        planning_horizon_days=horizon,
        price_impact_coef=1.0,
        replenish_cost_coef=0.05,
    )


def test_lp_returns_plan_with_expected_shape():
    plan = solve_spr_plan(make_config())
    assert plan.status in ("Optimal", "Not Solved", "Infeasible", "Unbounded")
    assert len(plan.days) == 14
    assert len(plan.drawdown_kbpd) == 14
    assert len(plan.replenish_kbpd) == 14
    assert len(plan.reserve_mmb) == 14
    assert len(plan.unmet_gap_kbpd) == 14


def test_lp_finds_optimal_when_gap_within_capacity():
    cfg = make_config(horizon=14, gap=500.0, reserve=39.0)
    plan = solve_spr_plan(cfg)
    assert plan.status == "Optimal"
    # Drawdown should bridge most of the gap.
    for d, u in zip(plan.drawdown_kbpd, plan.unmet_gap_kbpd):
        assert d + u >= 500.0 - 1e-3
        assert 0 <= d <= cfg.max_daily_drawdown_kbpd + 1e-6


def test_lp_respects_capacity_when_gap_exceeds_drawdown():
    cfg = make_config(horizon=14, gap=1500.0, reserve=39.0)
    plan = solve_spr_plan(cfg)
    # Drawdown is capped; unmet must absorb the rest.
    for d in plan.drawdown_kbpd:
        assert d <= cfg.max_daily_drawdown_kbpd + 1e-6
    for u in plan.unmet_gap_kbpd:
        assert u >= 1500.0 - cfg.max_daily_drawdown_kbpd - 1e-6


def test_reserve_never_negative():
    plan = solve_spr_plan(make_config())
    for r in plan.reserve_mmb:
        assert r >= -1e-6


def test_baseline_no_action_passes_entire_gap_through():
    cfg = make_config(horizon=14, gap=500.0)
    base = baseline_no_action_plan(cfg)
    assert all(d == 0.0 for d in base.drawdown_kbpd)
    assert all(r == cfg.starting_reserve_mmb for r in base.reserve_mmb)
    assert all(u == 500.0 for u in base.unmet_gap_kbpd)
    assert base.total_impact_score == pytest.approx(500.0 * 14 * cfg.price_impact_coef)


def test_lp_total_impact_at_or_below_baseline():
    cfg = make_config(horizon=14, gap=500.0, reserve=39.0)
    lp = solve_spr_plan(cfg)
    base = baseline_no_action_plan(cfg)
    # LP must do at least as well as no-action (gap-closed ratio >= 0).
    assert lp.total_impact_score <= base.total_impact_score + 1e-6


def test_zero_gap_means_no_action_needed():
    cfg = make_config(horizon=7, gap=0.0)
    plan = solve_spr_plan(cfg)
    for d in plan.drawdown_kbpd:
        assert d < 1e-6
    for u in plan.unmet_gap_kbpd:
        assert u < 1e-6


def test_negative_horizon_rejected():
    with pytest.raises(ValueError):
        SPRConfig(
            starting_reserve_mmb=39.0,
            max_daily_drawdown_kbpd=600.0,
            max_daily_replenish_kbpd=200.0,
            daily_consumption_kbpd=5100.0,
            supply_gap_curve=[],
            planning_horizon_days=0,
        )


def test_short_gap_curve_is_padded():
    cfg = SPRConfig(
        starting_reserve_mmb=39.0,
        max_daily_drawdown_kbpd=600.0,
        max_daily_replenish_kbpd=200.0,
        daily_consumption_kbpd=5100.0,
        supply_gap_curve=[300.0, 400.0],
        planning_horizon_days=10,
    )
    # Last value (400.0) padded to fill horizon.
    assert cfg.supply_gap_curve[-1] == 400.0
    assert len(cfg.supply_gap_curve) == 10
