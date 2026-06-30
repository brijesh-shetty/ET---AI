"""
Scenario modeller — single source of truth.

Seven named scenarios cover the dominant tail risks for India's strategic
import basket. Each scenario translates an input (intensity in [0, 1] and
duration in days) into a deterministic projection of:

  * Commodity price uplift (Brent, LNG, coking coal, plus a per-scenario
    "primary commodity" headline)
  * GDP drag in basis points, routed through each scenario's documented
    mechanism (crude import bill, steel margin, EV capex, renewable capex,
    nuclear capex, etc.)
  * SPR / stockpile runway (days of cover)
  * Sector trajectory deflections (refinery run-rate drop, power-sector
    stress rise) — drives the per-day timeline the API surfaces

All elasticities and transmission coefficients are documented in
`docs/assumptions.md`. The engine NEVER returns random numbers.

Previously this module exposed a separate `run_scenario()` Pydantic flow that
diverged from what the API actually served. That dead code is gone — the only
public entry point is `project_scenario(name, intensity, duration_days)`,
which the API route calls directly. The returned dict is the canonical
"impact" shape the route assembles its response from.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# Baseline India macro and commodity references (calendar 2025-26 averages).
# These are static inputs to the elasticity model — patched live at startup
# by `ingest/baselines.py` when an API call succeeds (Brent, LNG).
# See docs/assumptions.md for the calibration rationale.
BASELINE: dict[str, float] = {
    "brent_usd_bbl": 82.0,
    "ttf_eur_mwh": 34.0,
    "jkm_usd_mmbtu": 12.5,
    "coking_coal_usd_t": 235.0,
    "lithium_carbonate_usd_t": 14500.0,
    "neodymium_usd_kg": 78.0,
    "solar_module_usd_w": 0.11,
    "uranium_usd_lb": 86.0,
    "india_gdp_usd_tn": 4.10,
    "india_crude_import_mbd": 5.10,
    "india_lng_import_bcm": 32.0,
    "india_coking_coal_import_mt": 58.0,
    "spr_crude_mmb": 39.0,
    "spr_days_cover_at_baseline": 9.5,
}


@dataclass
class Scenario:
    name: str
    primary_commodity: str
    primary_corridor: str
    default_intensity: float
    default_duration_days: int
    params: dict[str, Any] = field(default_factory=dict)
    description: str = ""


SCENARIOS: dict[str, Scenario] = {
    "hormuz_partial_closure": Scenario(
        name="hormuz_partial_closure",
        primary_commodity="crude",
        primary_corridor="hormuz",
        default_intensity=0.40,
        default_duration_days=21,
        description=(
            "Partial closure of the Strait of Hormuz disrupting Gulf crude and "
            "Qatari LNG. ~40-45% of India's crude transits Hormuz."
        ),
        params={
            # Price elasticity of a 100% shock to imported volume at full intensity.
            "crude_price_elasticity": 0.55,
            "lng_price_elasticity": 0.40,
            "crude_volume_share": 0.42,
            "lng_volume_share": 0.48,
            "gdp_bps_per_10usd_brent": 18.0,
            "spr_drawdown_share": 0.65,
        },
    ),
    "opec_emergency_cut": Scenario(
        name="opec_emergency_cut",
        primary_commodity="crude",
        primary_corridor="hormuz",
        default_intensity=0.50,
        default_duration_days=60,
        description=(
            "OPEC+ emergency production cut. Modelled as a global supply shock "
            "transmitted to India via Brent."
        ),
        params={
            "crude_price_elasticity": 0.30,
            "global_cut_mbd_at_full": 3.0,
            "gdp_bps_per_10usd_brent": 18.0,
            "spr_drawdown_share": 0.50,
        },
    ),
    "red_sea_suspension": Scenario(
        name="red_sea_suspension",
        primary_commodity="container",
        primary_corridor="bab_el_mandeb",
        default_intensity=0.70,
        default_duration_days=45,
        description=(
            "Sustained Houthi attacks force suspension of Bab el-Mandeb / Suez "
            "transit. Container, crude and LNG reroute via Cape of Good Hope."
        ),
        params={
            "freight_uplift_pct_at_full": 145.0,
            "crude_price_elasticity": 0.18,
            "lng_price_elasticity": 0.22,
            "cape_detour_days": 14,
            "gdp_bps_per_10usd_brent": 18.0,
            "spr_drawdown_share": 0.20,
        },
    ),
    "australia_coking_coal": Scenario(
        name="australia_coking_coal",
        primary_commodity="coking_coal",
        primary_corridor="malacca",
        default_intensity=0.55,
        default_duration_days=30,
        description=(
            "Queensland coking-coal supply disruption (cyclone, rail outage or "
            "export curb). India imports ~70% of coking coal from Australia."
        ),
        params={
            "coking_coal_elasticity": 0.65,
            "australia_share": 0.70,
            "steel_output_drag_bps_per_10pct_price": 4.5,
            "stockpile_days": 22.0,
        },
    ),
    "china_rare_earth_curbs": Scenario(
        name="china_rare_earth_curbs",
        primary_commodity="rare_earth",
        primary_corridor="south_china_sea",
        default_intensity=0.60,
        default_duration_days=120,
        description=(
            "China tightens rare-earth export licensing, hitting Nd/Dy/Tb and "
            "downstream EV battery cathode supply. ~90% of India's REE comes "
            "from China."
        ),
        params={
            "ree_price_elasticity": 1.10,
            "china_share": 0.90,
            "ev_battery_pass_through_pct": 6.0,
            "gdp_bps_per_pp_ev_capex_drag": 1.2,
            "stockpile_days": 35.0,
        },
    ),
    "china_solar_export_tariff": Scenario(
        name="china_solar_export_tariff",
        primary_commodity="solar_pv",
        primary_corridor="south_china_sea",
        default_intensity=0.45,
        default_duration_days=180,
        description=(
            "China imposes export tariffs/quotas on PV modules and cells. India "
            "imports ~80% of modules and ~60% of cells from China."
        ),
        params={
            "module_price_elasticity": 0.35,
            "china_module_share": 0.80,
            "lcoe_uplift_pct_per_10pct_module": 3.8,
            "renewable_capex_drag_bps": 2.5,
            "stockpile_days": 60.0,
        },
    ),
    "kazakhstan_uranium_disruption": Scenario(
        name="kazakhstan_uranium_disruption",
        primary_commodity="uranium",
        primary_corridor="malacca",
        default_intensity=0.50,
        default_duration_days=90,
        description=(
            "Kazakh uranium supply disrupted (rail through Russia, or Kazatomprom "
            "force majeure). Kazakhstan supplies ~40% of global U3O8."
        ),
        params={
            "uranium_price_elasticity": 0.45,
            "kazakhstan_share": 0.40,
            "fuel_cycle_buffer_days": 540.0,
            "npp_capex_drag_bps": 0.8,
        },
    ),
}


# Per-scenario sector-transmission profile: how a unit of shock intensity
# propagates into India's *refining* and *power* sectors. Each value is the
# MAX deflection at full intensity (i=1.0) before duration scaling.
#   refinery_runrate_drop_pp : percentage points off refinery run rate (100% base)
#   power_stress_rise        : points added to the 0-100 power-sector stress index
# Rationale (why these differ by scenario, not just by the slider):
#   - Only crude/LNG (refinery feedstock) shocks cut run rates. Coking coal
#     feeds STEEL, not refineries -> 0. Rare earth / solar / uranium -> 0.
#   - Power stress is driven by gas-for-power (LNG) and grid-fuel shortfalls.
#     Coking coal is metallurgical, NOT thermal -> ~0 power impact. Uranium
#     feeds nuclear (~3% of generation) behind an ~18-month fuel buffer
#     -> small/slow.
SCENARIO_SECTOR_TRANSMISSION: dict[str, dict[str, float]] = {
    "hormuz_partial_closure":       {"refinery_runrate_drop_pp": 22.0, "power_stress_rise": 28.0},
    "opec_emergency_cut":           {"refinery_runrate_drop_pp": 8.0,  "power_stress_rise": 6.0},
    "red_sea_suspension":           {"refinery_runrate_drop_pp": 5.0,  "power_stress_rise": 8.0},
    "australia_coking_coal":        {"refinery_runrate_drop_pp": 0.0,  "power_stress_rise": 2.0},
    "china_rare_earth_curbs":       {"refinery_runrate_drop_pp": 0.0,  "power_stress_rise": 3.0},
    "china_solar_export_tariff":    {"refinery_runrate_drop_pp": 0.0,  "power_stress_rise": 4.0},
    "kazakhstan_uranium_disruption":{"refinery_runrate_drop_pp": 0.0,  "power_stress_rise": 6.0},
}


def _intensity(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def _duration_factor(days: int) -> float:
    """Sublinear scaling: short shocks are absorbed by inventories, longer
    shocks saturate as substitution kicks in. Reaches 1.0 at ~14 days, capped."""
    d = max(int(days), 1)
    return min(1.0, (d / 14.0) ** 0.6)


def project_scenario(
    name: str,
    intensity: float,
    duration_days: int,
    *,
    brent_baseline: float | None = None,
    spr_baseline_days: float | None = None,
) -> dict[str, float]:
    """Project a named scenario's macro impact from its *documented* SCENARIOS
    params. Returns the canonical impact dict the API route consumes:

        brent_uplift_pct, lng_uplift_pct, coal_uplift_pct, primary_uplift_pct
        gdp_bps                  (negative = drag)
        spr_runway_days          (post-shock SPR cover)
        refinery_drop_pp         (intensity- and duration-scaled deflection)
        power_stress_rise        (intensity- and duration-scaled deflection)

    Non-oil scenarios surface a `primary_uplift_pct` headline for their own
    commodity and still register a GDP drag via the scenario's documented
    capex/output channel.

    Parameters
    ----------
    name
        Key in SCENARIOS. Raises KeyError if unknown.
    intensity
        Shock severity in [0, 1]. Clipped if out of range.
    duration_days
        Disruption window. Must be > 0.
    brent_baseline
        Override the live Brent baseline. Defaults to BASELINE["brent_usd_bbl"]
        (which `ingest/baselines.py` patches live at startup).
    spr_baseline_days
        Override the SPR cover days baseline. Defaults to
        BASELINE["spr_days_cover_at_baseline"].
    """
    if name not in SCENARIOS:
        raise KeyError(f"unknown scenario: {name}")

    scenario = SCENARIOS[name]
    p = scenario.params
    dur = _duration_factor(duration_days)
    i = _intensity(intensity)
    gpb = p.get("gdp_bps_per_10usd_brent", 18.0)
    brent = float(brent_baseline) if brent_baseline is not None else BASELINE["brent_usd_bbl"]
    spr_base = float(spr_baseline_days) if spr_baseline_days is not None else BASELINE["spr_days_cover_at_baseline"]

    brent_uplift = 0.0
    lng_uplift = 0.0
    coal_uplift = 0.0
    primary_uplift = 0.0
    gdp_bps = 0.0

    if name == "hormuz_partial_closure":
        brent_uplift = 100.0 * p["crude_price_elasticity"] * i * p["crude_volume_share"]
        lng_uplift = 100.0 * p["lng_price_elasticity"] * i * p["lng_volume_share"]
    elif name == "opec_emergency_cut":
        # Realised cut scales linearly with intensity; uplift via documented elasticity.
        brent_uplift = 100.0 * p["crude_price_elasticity"] * i
    elif name == "red_sea_suspension":
        # Rerouting/freight-driven uplift (no physical supply loss) on crude + LNG.
        brent_uplift = 100.0 * p["crude_price_elasticity"] * i
        lng_uplift = 100.0 * p["lng_price_elasticity"] * i
    elif name == "australia_coking_coal":
        coal_uplift = 100.0 * p["coking_coal_elasticity"] * i * p["australia_share"]
    elif name == "china_rare_earth_curbs":
        primary_uplift = 100.0 * p["ree_price_elasticity"] * i * p["china_share"]
    elif name == "china_solar_export_tariff":
        primary_uplift = 100.0 * p["module_price_elasticity"] * i * p["china_module_share"]
    elif name == "kazakhstan_uranium_disruption":
        primary_uplift = 100.0 * p["uranium_price_elasticity"] * i * p["kazakhstan_share"]

    brent_uplift *= dur
    lng_uplift *= dur
    coal_uplift *= dur
    primary_uplift *= dur

    # GDP drag (negative bps) routed through each scenario's OWN channel.
    delta_brent = brent * brent_uplift / 100.0
    if name in ("hormuz_partial_closure", "opec_emergency_cut", "red_sea_suspension"):
        gdp_bps = -((delta_brent / 10.0) * gpb + lng_uplift * 0.6)
    elif name == "australia_coking_coal":
        gdp_bps = -(coal_uplift / 10.0) * p.get("steel_output_drag_bps_per_10pct_price", 4.5)
    elif name == "china_rare_earth_curbs":
        gdp_bps = -p.get("gdp_bps_per_pp_ev_capex_drag", 1.2) * p.get("ev_battery_pass_through_pct", 6.0) * i * dur
    elif name == "china_solar_export_tariff":
        gdp_bps = -p.get("renewable_capex_drag_bps", 2.5) * i * dur
    elif name == "kazakhstan_uranium_disruption":
        gdp_bps = -p.get("npp_capex_drag_bps", 0.8) * i * dur

    spr_runway = max(2.0, spr_base - (brent_uplift / 10.0))
    tx = SCENARIO_SECTOR_TRANSMISSION.get(
        name, {"refinery_runrate_drop_pp": 0.0, "power_stress_rise": 0.0}
    )
    return {
        "brent_uplift_pct": round(brent_uplift, 2),
        "lng_uplift_pct": round(lng_uplift, 2),
        "coal_uplift_pct": round(coal_uplift, 2),
        "primary_uplift_pct": round(primary_uplift, 2),
        "gdp_bps": round(gdp_bps, 1),
        "spr_runway_days": round(spr_runway, 1),
        "refinery_drop_pp": round(tx["refinery_runrate_drop_pp"] * i * dur, 2),
        "power_stress_rise": round(tx["power_stress_rise"] * i * dur, 2),
    }
