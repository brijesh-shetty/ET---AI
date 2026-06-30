"""Strategic Petroleum Reserve drawdown optimization.

Linear program that decides daily SPR drawdown and replenishment levels to
minimize the price-impact-weighted supply deficit over a planning horizon,
subject to reserve balance, capacity, and non-negativity constraints.

The model is intentionally simple: a single aggregate reserve pool, a single
crude grade, and a price impact coefficient that is constant per unit of
unmet demand. This is the right altitude for a planning dashboard; a true
operations model would split by depot (Vizag, Mangalore, Padur), grade, and
refinery offtake contracts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class SPRConfig:
    """Inputs to the SPR drawdown LP.

    Reserves and capacities are expressed in million barrels (MMb) and
    thousand barrels per day (kbpd) respectively, matching PPAC bulletin
    conventions.
    """

    starting_reserve_mmb: float
    max_daily_drawdown_kbpd: float
    max_daily_replenish_kbpd: float
    daily_consumption_kbpd: float
    supply_gap_curve: List[float]
    planning_horizon_days: int
    price_impact_coef: float = 1.0
    replenish_cost_coef: float = 0.05
    # Soft floor: reserve we want to keep in the tank. Dropping below it is
    # allowed (so the LP never goes infeasible) but penalised, so a higher
    # target cover makes the plan draw down more conservatively / rebuild faster.
    reserve_floor_mmb: float = 0.0
    floor_penalty_coef: float = 0.4
    # Physical tank ceiling (Mbbl); 0 means uncapped. Reserve cannot exceed it.
    capacity_mmb: float = 0.0
    # Per-day mask of when replenishment is permitted (a replenishment window).
    # None means "any day the supply gap is zero" is treated as a window.
    replenish_allowed: Optional[List[bool]] = None
    # Reward (per Mbbl) for the reserve standing at the end of the horizon, so the
    # LP refills in a replenishment window after the shock rather than ending at
    # the trough. Kept below the unmet-shortfall weight so it never starves the
    # live drawdown.
    rebuild_reward_coef: float = 0.0

    def __post_init__(self) -> None:
        if self.planning_horizon_days <= 0:
            raise ValueError("planning_horizon_days must be positive")
        if len(self.supply_gap_curve) < self.planning_horizon_days:
            # Pad with the trailing value so callers can pass a shorter curve.
            tail = self.supply_gap_curve[-1] if self.supply_gap_curve else 0.0
            pad = [tail] * (self.planning_horizon_days - len(self.supply_gap_curve))
            self.supply_gap_curve = list(self.supply_gap_curve) + pad


@dataclass
class SPRPlan:
    """Output of the SPR LP or its no-action baseline."""

    days: List[int]
    drawdown_kbpd: List[float]
    replenish_kbpd: List[float]
    reserve_mmb: List[float]
    unmet_gap_kbpd: List[float]
    total_impact_score: float
    objective_value: float
    status: str
    notes: List[str] = field(default_factory=list)


def _kbpd_to_mmb_per_day(kbpd: float) -> float:
    """Convert thousand bpd to million barrels per day."""
    return kbpd / 1000.0


def solve_spr_plan(config: SPRConfig) -> SPRPlan:
    """Solve the SPR drawdown LP with CBC.

    Decision variables for each day t in [0, horizon):
      drawdown_d[t]  in [0, max_daily_drawdown_kbpd]
      replenish_r[t] in [0, max_daily_replenish_kbpd]
      unmet_u[t]     in [0, supply_gap_curve[t]]

    Reserve balance (in MMb):
      reserve[0]   = starting_reserve_mmb - d[0]/1000 + r[0]/1000
      reserve[t]   = reserve[t-1]         - d[t]/1000 + r[t]/1000
      reserve[t]  >= 0

    Supply balance (in kbpd):
      d[t] - r[t] + u[t] = supply_gap_curve[t]
      (drawdown plus unmet shortfall must cover the gap; replenish eats into
      available crude when markets are loose and we are rebuilding.)

    Objective:
      minimize sum_t ( price_impact_coef * u[t]
                       + replenish_cost_coef * r[t] )
    """
    import pulp

    horizon = config.planning_horizon_days
    gap = config.supply_gap_curve

    prob = pulp.LpProblem("spr_drawdown", pulp.LpMinimize)

    # Replenishment is only permitted inside a window. Default: any day the
    # supply gap has cleared (you don't refill mid-shortage).
    if config.replenish_allowed is not None:
        allowed = list(config.replenish_allowed)
    else:
        allowed = [gap[t] <= 0.0 for t in range(horizon)]

    d = [
        pulp.LpVariable(f"d_{t}", lowBound=0.0, upBound=config.max_daily_drawdown_kbpd)
        for t in range(horizon)
    ]
    r = [
        pulp.LpVariable(
            f"r_{t}",
            lowBound=0.0,
            upBound=config.max_daily_replenish_kbpd if (t < len(allowed) and allowed[t]) else 0.0,
        )
        for t in range(horizon)
    ]
    u = [
        pulp.LpVariable(f"u_{t}", lowBound=0.0, upBound=max(0.0, gap[t]))
        for t in range(horizon)
    ]
    reserve_ub = config.capacity_mmb if config.capacity_mmb > 0 else None
    reserve = [
        pulp.LpVariable(f"sp_{t}", lowBound=0.0, upBound=reserve_ub) for t in range(horizon)
    ]

    use_floor = config.reserve_floor_mmb > 0.0
    # Slack for dropping below the desired reserve floor (only when a floor is set).
    floor_short = (
        [pulp.LpVariable(f"fs_{t}", lowBound=0.0) for t in range(horizon)]
        if use_floor
        else None
    )

    objective = pulp.lpSum(
        config.price_impact_coef * u[t] + config.replenish_cost_coef * r[t]
        for t in range(horizon)
    )
    if use_floor and floor_short is not None:
        objective += pulp.lpSum(
            config.floor_penalty_coef * floor_short[t] for t in range(horizon)
        )
    if config.rebuild_reward_coef > 0.0 and horizon > 0:
        # Reward end-of-horizon reserve so post-shock windows are used to refill.
        objective += -config.rebuild_reward_coef * reserve[horizon - 1]
    prob += objective

    for t in range(horizon):
        prev = config.starting_reserve_mmb if t == 0 else reserve[t - 1]
        prob += (
            reserve[t]
            == prev - _kbpd_to_mmb_per_day(d[t]) + _kbpd_to_mmb_per_day(r[t])
        ), f"reserve_balance_{t}"
        # Drawdown plus unmet shortfall must cover the day's gap. Replenishment
        # is independent (it rebuilds the tank during a window), not a way to
        # cover a live shortfall.
        prob += d[t] + u[t] == max(0.0, gap[t]), f"supply_balance_{t}"
        if use_floor and floor_short is not None:
            # reserve[t] + floor_short[t] >= floor  →  shortfall penalised
            prob += (
                reserve[t] + floor_short[t] >= config.reserve_floor_mmb
            ), f"reserve_floor_{t}"

    solver = pulp.PULP_CBC_CMD(msg=False)
    prob.solve(solver)

    status = pulp.LpStatus[prob.status]
    drawdown_series = [float(v.value() or 0.0) for v in d]
    replenish_series = [float(v.value() or 0.0) for v in r]
    reserve_series = [float(v.value() or 0.0) for v in reserve]
    unmet_series = [float(v.value() or 0.0) for v in u]
    total_impact = sum(unmet_series) * config.price_impact_coef
    objective = float(pulp.value(prob.objective) or 0.0)

    notes = []
    if any(v <= 1e-6 for v in reserve_series):
        notes.append("Reserve hits zero in the planning window; gap exceeds capacity.")
    if all(d_t <= 1e-6 for d_t in drawdown_series):
        notes.append("LP elected not to draw down; supply gap is within absorbable range.")

    return SPRPlan(
        days=list(range(horizon)),
        drawdown_kbpd=drawdown_series,
        replenish_kbpd=replenish_series,
        reserve_mmb=reserve_series,
        unmet_gap_kbpd=unmet_series,
        total_impact_score=total_impact,
        objective_value=objective,
        status=status,
        notes=notes,
    )


def baseline_no_action_plan(config: SPRConfig) -> SPRPlan:
    """Counterfactual: no SPR action, the observed gap is fully unmet.

    Used by the UI to quantify the LP's contribution — total_impact_score
    of the LP plan divided by this baseline gives a "gap closed" ratio.
    """
    horizon = config.planning_horizon_days
    gap = config.supply_gap_curve

    drawdown = [0.0] * horizon
    replenish = [0.0] * horizon
    reserve = [config.starting_reserve_mmb] * horizon
    unmet = [max(0.0, gap[t]) for t in range(horizon)]
    total_impact = sum(unmet) * config.price_impact_coef

    return SPRPlan(
        days=list(range(horizon)),
        drawdown_kbpd=drawdown,
        replenish_kbpd=replenish,
        reserve_mmb=reserve,
        unmet_gap_kbpd=unmet,
        total_impact_score=total_impact,
        objective_value=total_impact,
        status="Baseline",
        notes=["No SPR action taken; the full supply gap flows through to price."],
    )
