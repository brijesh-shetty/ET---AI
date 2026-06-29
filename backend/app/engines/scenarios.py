"""
Scenario modeller.

Seven named scenarios cover the dominant tail risks for India's strategic
import basket. Each scenario translates an input (intensity in [0, 1] and
duration in days) into a deterministic projection of price uplift, GDP drag,
and SPR/stockpile runway. The elasticities are documented in
docs/assumptions.md; this module never returns random numbers.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.models import ScenarioResult


# Baseline India macro and commodity references (calendar 2025-26 averages).
# These are static inputs to the elasticity model. See assumptions.md.
BASELINE = {
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


def _intensity(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def _duration_factor(days: int) -> float:
    """
    Sublinear scaling with duration: short shocks are absorbed by inventories,
    long shocks are partly mitigated by substitution. Saturates near 1.5x.
    """
    d = max(int(days), 1)
    return 1.0 - 0.5 ** (d / 30.0) + 0.5  # 30-day half-life centered at 1.0


def _round(value: float, places: int = 2) -> float:
    return round(float(value), places)


async def run_scenario(name: str, intensity: float, duration_days: int) -> ScenarioResult:
    """
    Project the cascading impact of a named scenario.

    Parameters
    ----------
    name : str
        Key in SCENARIOS.
    intensity : float
        Shock intensity in [0, 1]. 1.0 = full closure / total embargo.
    duration_days : int
        Disruption duration in days.

    Returns
    -------
    ScenarioResult
        Includes price uplifts (USD and %), GDP-bps drag, SPR / stockpile
        runway after the shock, and a list of narrative bullets.
    """
    if name not in SCENARIOS:
        raise ValueError(f"unknown scenario: {name}")

    scenario = SCENARIOS[name]
    i = _intensity(intensity)
    dur_factor = _duration_factor(duration_days)

    # Yield to the event loop so callers can fan out scenarios concurrently
    # without blocking. The math itself is pure CPU but cheap.
    await asyncio.sleep(0)

    if name == "hormuz_partial_closure":
        impact = _hormuz_partial_closure(scenario, i, dur_factor, duration_days)
    elif name == "opec_emergency_cut":
        impact = _opec_emergency_cut(scenario, i, dur_factor, duration_days)
    elif name == "red_sea_suspension":
        impact = _red_sea_suspension(scenario, i, dur_factor, duration_days)
    elif name == "australia_coking_coal":
        impact = _australia_coking_coal(scenario, i, dur_factor, duration_days)
    elif name == "china_rare_earth_curbs":
        impact = _china_rare_earth_curbs(scenario, i, dur_factor, duration_days)
    elif name == "china_solar_export_tariff":
        impact = _china_solar_export_tariff(scenario, i, dur_factor, duration_days)
    elif name == "kazakhstan_uranium_disruption":
        impact = _kazakhstan_uranium_disruption(scenario, i, dur_factor, duration_days)
    else:  # defensive; SCENARIOS membership already checked above
        raise ValueError(f"unhandled scenario: {name}")

    return ScenarioResult(
        scenario=name,
        intensity=i,
        duration_days=duration_days,
        primary_commodity=scenario.primary_commodity,
        primary_corridor=scenario.primary_corridor,
        price_impacts=impact["price_impacts"],
        gdp_bps=impact["gdp_bps"],
        runway_days=impact["runway_days"],
        narrative=impact["narrative"],
        computed_at=datetime.now(timezone.utc),
    )


def _hormuz_partial_closure(s: Scenario, i: float, dur_factor: float, days: int) -> dict:
    p = s.params
    crude_uplift_pct = 100.0 * p["crude_price_elasticity"] * i * p["crude_volume_share"] * dur_factor
    lng_uplift_pct = 100.0 * p["lng_price_elasticity"] * i * p["lng_volume_share"] * dur_factor
    brent_new = BASELINE["brent_usd_bbl"] * (1.0 + crude_uplift_pct / 100.0)
    jkm_new = BASELINE["jkm_usd_mmbtu"] * (1.0 + lng_uplift_pct / 100.0)
    delta_brent = brent_new - BASELINE["brent_usd_bbl"]
    gdp_bps = (delta_brent / 10.0) * p["gdp_bps_per_10usd_brent"]

    spr_days = BASELINE["spr_days_cover_at_baseline"] / max(p["spr_drawdown_share"] * i + 0.25, 0.25)

    return {
        "price_impacts": [
            {"commodity": "crude", "baseline": BASELINE["brent_usd_bbl"], "new": _round(brent_new), "pct": _round(crude_uplift_pct)},
            {"commodity": "lng_jkm", "baseline": BASELINE["jkm_usd_mmbtu"], "new": _round(jkm_new), "pct": _round(lng_uplift_pct)},
        ],
        "gdp_bps": _round(gdp_bps),
        "runway_days": _round(spr_days),
        "narrative": [
            f"Brent projected at ${brent_new:.1f}/bbl (+{crude_uplift_pct:.1f}%) for {days} days.",
            f"JKM LNG projected at ${jkm_new:.1f}/mmbtu (+{lng_uplift_pct:.1f}%).",
            f"Indian SPR runway compresses to ~{spr_days:.1f} days of net imports.",
            f"GDP drag of ~{gdp_bps:.0f} bps if shock persists at intensity {i:.0%}.",
        ],
    }


def _opec_emergency_cut(s: Scenario, i: float, dur_factor: float, days: int) -> dict:
    p = s.params
    cut_mbd = p["global_cut_mbd_at_full"] * i
    uplift_pct = 100.0 * p["crude_price_elasticity"] * (cut_mbd / 3.0) * dur_factor
    brent_new = BASELINE["brent_usd_bbl"] * (1.0 + uplift_pct / 100.0)
    delta_brent = brent_new - BASELINE["brent_usd_bbl"]
    gdp_bps = (delta_brent / 10.0) * p["gdp_bps_per_10usd_brent"]
    spr_days = BASELINE["spr_days_cover_at_baseline"] / max(p["spr_drawdown_share"] * i + 0.30, 0.30)

    return {
        "price_impacts": [
            {"commodity": "crude", "baseline": BASELINE["brent_usd_bbl"], "new": _round(brent_new), "pct": _round(uplift_pct)},
        ],
        "gdp_bps": _round(gdp_bps),
        "runway_days": _round(spr_days),
        "narrative": [
            f"OPEC+ withdraws ~{cut_mbd:.1f} mbd of supply for {days} days.",
            f"Brent projected at ${brent_new:.1f}/bbl (+{uplift_pct:.1f}%).",
            f"GDP drag of ~{gdp_bps:.0f} bps via import bill widening.",
            f"SPR runway compresses to ~{spr_days:.1f} days.",
        ],
    }


def _red_sea_suspension(s: Scenario, i: float, dur_factor: float, days: int) -> dict:
    p = s.params
    freight_uplift_pct = p["freight_uplift_pct_at_full"] * i * dur_factor
    crude_uplift_pct = 100.0 * p["crude_price_elasticity"] * i * dur_factor
    lng_uplift_pct = 100.0 * p["lng_price_elasticity"] * i * dur_factor
    brent_new = BASELINE["brent_usd_bbl"] * (1.0 + crude_uplift_pct / 100.0)
    jkm_new = BASELINE["jkm_usd_mmbtu"] * (1.0 + lng_uplift_pct / 100.0)
    delta_brent = brent_new - BASELINE["brent_usd_bbl"]
    gdp_bps = (delta_brent / 10.0) * p["gdp_bps_per_10usd_brent"] + 2.0 * (freight_uplift_pct / 100.0)
    spr_days = BASELINE["spr_days_cover_at_baseline"] / max(p["spr_drawdown_share"] * i + 0.40, 0.40)

    return {
        "price_impacts": [
            {"commodity": "container_freight", "baseline": 100.0, "new": _round(100.0 + freight_uplift_pct), "pct": _round(freight_uplift_pct)},
            {"commodity": "crude", "baseline": BASELINE["brent_usd_bbl"], "new": _round(brent_new), "pct": _round(crude_uplift_pct)},
            {"commodity": "lng_jkm", "baseline": BASELINE["jkm_usd_mmbtu"], "new": _round(jkm_new), "pct": _round(lng_uplift_pct)},
        ],
        "gdp_bps": _round(gdp_bps),
        "runway_days": _round(spr_days),
        "narrative": [
            f"Suez transit suspended; reroute via Cape adds ~{p['cape_detour_days']} voyage days.",
            f"Container freight index up ~{freight_uplift_pct:.0f}% above baseline.",
            f"Brent at ${brent_new:.1f}/bbl (+{crude_uplift_pct:.1f}%), JKM at ${jkm_new:.1f}/mmbtu.",
            f"Combined GDP drag of ~{gdp_bps:.0f} bps.",
        ],
    }


def _australia_coking_coal(s: Scenario, i: float, dur_factor: float, days: int) -> dict:
    p = s.params
    uplift_pct = 100.0 * p["coking_coal_elasticity"] * i * p["australia_share"] * dur_factor
    cc_new = BASELINE["coking_coal_usd_t"] * (1.0 + uplift_pct / 100.0)
    steel_drag_bps = (uplift_pct / 10.0) * p["steel_output_drag_bps_per_10pct_price"]
    runway = p["stockpile_days"] / max(i + 0.20, 0.20)

    return {
        "price_impacts": [
            {"commodity": "coking_coal", "baseline": BASELINE["coking_coal_usd_t"], "new": _round(cc_new), "pct": _round(uplift_pct)},
        ],
        "gdp_bps": _round(steel_drag_bps),
        "runway_days": _round(runway),
        "narrative": [
            f"Coking coal projected at ${cc_new:.0f}/t (+{uplift_pct:.1f}%) for {days} days.",
            f"Steel-sector value-add drag of ~{steel_drag_bps:.0f} bps to GDP.",
            f"Indian mill stockpiles run ~{runway:.0f} days before forced cuts.",
            "Alternative sourcing: US Appalachian, Mozambique, Russia — all higher freight cost.",
        ],
    }


def _china_rare_earth_curbs(s: Scenario, i: float, dur_factor: float, days: int) -> dict:
    p = s.params
    uplift_pct = 100.0 * p["ree_price_elasticity"] * i * p["china_share"] * dur_factor
    nd_new = BASELINE["neodymium_usd_kg"] * (1.0 + uplift_pct / 100.0)
    ev_pass_pct = p["ev_battery_pass_through_pct"] * i * dur_factor
    gdp_bps = ev_pass_pct * p["gdp_bps_per_pp_ev_capex_drag"]
    runway = p["stockpile_days"] / max(i + 0.30, 0.30)

    return {
        "price_impacts": [
            {"commodity": "neodymium", "baseline": BASELINE["neodymium_usd_kg"], "new": _round(nd_new), "pct": _round(uplift_pct)},
        ],
        "gdp_bps": _round(gdp_bps),
        "runway_days": _round(runway),
        "narrative": [
            f"Neodymium projected at ${nd_new:.0f}/kg (+{uplift_pct:.0f}%) for {days} days.",
            f"EV battery and traction-motor pass-through ~{ev_pass_pct:.1f}%.",
            f"Renewable + EV capex drag of ~{gdp_bps:.1f} bps.",
            f"Domestic + non-China REE buffer ~{runway:.0f} days.",
        ],
    }


def _china_solar_export_tariff(s: Scenario, i: float, dur_factor: float, days: int) -> dict:
    p = s.params
    uplift_pct = 100.0 * p["module_price_elasticity"] * i * p["china_module_share"] * dur_factor
    mod_new = BASELINE["solar_module_usd_w"] * (1.0 + uplift_pct / 100.0)
    lcoe_uplift_pct = (uplift_pct / 10.0) * p["lcoe_uplift_pct_per_10pct_module"]
    gdp_bps = p["renewable_capex_drag_bps"] * i * dur_factor
    runway = p["stockpile_days"] / max(i + 0.40, 0.40)

    return {
        "price_impacts": [
            {"commodity": "solar_module", "baseline": BASELINE["solar_module_usd_w"], "new": _round(mod_new, 3), "pct": _round(uplift_pct)},
        ],
        "gdp_bps": _round(gdp_bps),
        "runway_days": _round(runway),
        "narrative": [
            f"PV module projected at ${mod_new:.3f}/W (+{uplift_pct:.1f}%) for {days} days.",
            f"Utility-scale solar LCOE up ~{lcoe_uplift_pct:.1f}%.",
            f"FY renewable capex drag of ~{gdp_bps:.1f} bps to GDP.",
            f"Module inventory buffer ~{runway:.0f} days at current build rate.",
        ],
    }


def _kazakhstan_uranium_disruption(s: Scenario, i: float, dur_factor: float, days: int) -> dict:
    p = s.params
    uplift_pct = 100.0 * p["uranium_price_elasticity"] * i * p["kazakhstan_share"] * dur_factor
    u_new = BASELINE["uranium_usd_lb"] * (1.0 + uplift_pct / 100.0)
    runway = p["fuel_cycle_buffer_days"] / max(i + 0.50, 0.50)
    gdp_bps = p["npp_capex_drag_bps"] * i * dur_factor

    return {
        "price_impacts": [
            {"commodity": "uranium_u3o8", "baseline": BASELINE["uranium_usd_lb"], "new": _round(u_new), "pct": _round(uplift_pct)},
        ],
        "gdp_bps": _round(gdp_bps),
        "runway_days": _round(runway),
        "narrative": [
            f"U3O8 projected at ${u_new:.0f}/lb (+{uplift_pct:.0f}%) for {days} days.",
            f"Indian fuel-cycle buffer ~{runway:.0f} days — no immediate generation risk.",
            f"NPP build pipeline capex drag ~{gdp_bps:.1f} bps.",
            "Alternative sources: Cameco (Canada), Orano (Niger), Rosatom (subject to sanctions).",
        ],
    }


def impact_table(result: ScenarioResult) -> list[dict]:
    """Flatten a ScenarioResult into a list of display rows."""
    rows: list[dict] = []
    for item in result.price_impacts:
        rows.append({
            "metric": f"Price: {item['commodity']}",
            "baseline": item["baseline"],
            "projected": item["new"],
            "delta_pct": item["pct"],
            "unit": _unit_for(item["commodity"]),
        })
    rows.append({
        "metric": "GDP impact",
        "baseline": 0.0,
        "projected": result.gdp_bps,
        "delta_pct": None,
        "unit": "bps",
    })
    rows.append({
        "metric": "Stockpile / SPR runway",
        "baseline": None,
        "projected": result.runway_days,
        "delta_pct": None,
        "unit": "days",
    })
    return rows


def _unit_for(commodity: str) -> str:
    return {
        "crude": "USD/bbl",
        "lng_jkm": "USD/mmbtu",
        "container_freight": "index",
        "coking_coal": "USD/t",
        "neodymium": "USD/kg",
        "solar_module": "USD/W",
        "uranium_u3o8": "USD/lb",
    }.get(commodity, "USD")
