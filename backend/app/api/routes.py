"""HTTP surface for the resilience platform.

Mounted under /api by main.py. Endpoints return JSON dicts in camelCase to
match the React frontend's TypeScript contract directly. The backend models
in app.models are used internally where convenient; over-the-wire shapes are
defined here to keep API/UI alignment explicit.

Run with: uvicorn app.main:app --reload --port 8000
Swagger docs: http://localhost:8000/docs
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.config import get_settings
from app.engines import scenarios as scenarios_engine
from app.engines import sourcing as sourcing_engine
from app.engines import spr_lp as spr_engine
from app.engines.scenarios import SCENARIOS
from app.models import Commodity, Corridor

router = APIRouter(tags=["resilience"])


CORRIDOR_FOR_COMMODITY: dict[str, str] = {
    "crude_oil": "hormuz",
    "lpg": "hormuz",
    "lng": "hormuz",
    "atf": "hormuz",
    "coking_coal": "malacca",
    "rare_earths": "south_china_sea",
    "lithium": "south_china_sea",
    "cobalt": "malacca",
    "nickel": "malacca",
    "solar_pv": "south_china_sea",
    "uranium": "malacca",
}

BASE_BRENT = 82.0
BASE_SPR_DAYS = 9.5
BASE_IMPORT_COST_USDM = 320.0

ALL_COMMODITIES: list[str] = [
    "crude_oil",
    "lng",
    "coking_coal",
    "lithium",
    "cobalt",
    "nickel",
    "rare_earths",
    "solar_pv",
    "uranium",
    "lpg",
    "atf",
]

CORRIDOR_LABEL: dict[str, str] = {
    "hormuz": "Strait of Hormuz",
    "bab_el_mandeb": "Bab el-Mandeb / Red Sea",
    "malacca": "Strait of Malacca",
    "south_china_sea": "South China Sea",
    "cape_of_good_hope": "Cape of Good Hope",
    "suez": "Suez Canal",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fixtures_dir() -> Path:
    return Path(get_settings().fixtures_path)


def _load_fixture(name: str) -> Any:
    path = _fixtures_dir() / name
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _tier(score: float) -> str:
    if score < 30:
        return "low"
    if score < 55:
        return "elevated"
    if score < 75:
        return "high"
    return "critical"


def _seeded_score(corridor: str, commodity: str) -> float:
    seed_map = {
        ("hormuz", "crude_oil"): 62,
        ("hormuz", "lng"): 58,
        ("hormuz", "lpg"): 55,
        ("bab_el_mandeb", "crude_oil"): 48,
        ("bab_el_mandeb", "lng"): 44,
        ("malacca", "coking_coal"): 36,
        ("malacca", "nickel"): 41,
        ("malacca", "cobalt"): 38,
        ("malacca", "uranium"): 22,
        ("south_china_sea", "rare_earths"): 64,
        ("south_china_sea", "solar_pv"): 51,
        ("south_china_sea", "lithium"): 47,
        ("cape_of_good_hope", "crude_oil"): 18,
        ("suez", "crude_oil"): 33,
    }
    return float(seed_map.get((corridor, commodity), 30))


def _risk_score_dict(corridor: str, commodity: str, score: float) -> dict:
    tier = _tier(score)
    geo = round(score * 0.40, 1)
    chokepoint = round(score * 0.25, 1)
    weather = round(score * 0.10, 1)
    market = round(score * 0.15, 1)
    sanctions = round(score * 0.10, 1)
    drivers = _drivers_for(corridor, commodity, score)
    return {
        "corridor": corridor,
        "commodity": commodity,
        "score": round(score, 1),
        "tier": tier,
        "components": {
            "geopolitical": geo,
            "chokepoint": chokepoint,
            "weather": weather,
            "market": market,
            "sanctions": sanctions,
        },
        "drivers": drivers,
        "confidence": 0.78,
        "asOf": _now_iso(),
    }


def _drivers_for(corridor: str, commodity: str, score: float) -> list[str]:
    base = []
    if corridor == "hormuz":
        base = [
            "GDELT: US-Iran tension signals last 24h",
            "AIS density 1.4 sigma above 90-day mean",
            f"Brent volatility {round(score / 15, 1)}% intraday",
        ]
    elif corridor == "bab_el_mandeb":
        base = [
            "Houthi statements in last 12h",
            "Suez transit count down 22% week-on-week",
            "Container freight uplift 8%",
        ]
    elif corridor == "malacca":
        base = [
            "Queensland weather signal (coal disruption tracker)",
            "Indonesia nickel export policy headlines",
            "Steel sector margin compression alerts",
        ]
    elif corridor == "south_china_sea":
        base = [
            "China rare-earth export controls in effect",
            "PV module export tariff retaliation risk",
            "Lithium spot tightening",
        ]
    else:
        base = [
            f"{CORRIDOR_LABEL.get(corridor, corridor)} corridor baseline",
            f"Composite score {round(score, 1)}",
        ]
    return base


@router.get("/healthz")
async def healthz() -> dict:
    settings = get_settings()
    fixtures = list(_fixtures_dir().glob("*.json")) if _fixtures_dir().exists() else []
    return {
        "status": "ok",
        "version": "0.1.0",
        "uptimeSeconds": 0,
        "dependencies": {
            "anthropic": "ok" if settings.anthropic_api_key else "down",
            "aisstream": "ok" if settings.ais_stream_api_key else "down",
            "fixtures": "ok" if fixtures else "down",
        },
        "asOf": _now_iso(),
        "liveIngest": settings.allow_live_ingest,
        "fixturesLoaded": len(fixtures),
    }


@router.get("/scores")
async def get_scores(commodity: str | None = Query(default=None)) -> list[dict]:
    pairs = [
        ("hormuz", "crude_oil"),
        ("hormuz", "lng"),
        ("hormuz", "lpg"),
        ("bab_el_mandeb", "crude_oil"),
        ("bab_el_mandeb", "lng"),
        ("malacca", "coking_coal"),
        ("malacca", "nickel"),
        ("malacca", "cobalt"),
        ("malacca", "uranium"),
        ("south_china_sea", "rare_earths"),
        ("south_china_sea", "solar_pv"),
        ("south_china_sea", "lithium"),
        ("cape_of_good_hope", "crude_oil"),
        ("suez", "crude_oil"),
    ]
    if commodity:
        pairs = [(c, k) for (c, k) in pairs if k == commodity]
    out: list[dict] = []
    for corridor, comm in pairs:
        score = _seeded_score(corridor, comm)
        out.append(_risk_score_dict(corridor, comm, score))
    return out


@router.get("/scores/{corridor}")
async def get_scores_by_corridor(corridor: str) -> list[dict]:
    all_scores = await get_scores()
    return [s for s in all_scores if s["corridor"] == corridor]


@router.get("/scenarios")
async def list_scenarios() -> list[dict]:
    out: list[dict] = []
    for name, sc in SCENARIOS.items():
        corridor = sc.params.get("primary_corridor", "hormuz") if hasattr(sc, "params") else "hormuz"
        commodity = sc.primary_commodity if hasattr(sc, "primary_commodity") else "crude_oil"
        out.append({
            "scenarioId": name,
            "name": _humanize(name),
            "description": _scenario_description(name),
            "corridor": _scenario_corridor(name),
            "commodity": _enum_value(commodity),
        })
    return out


def _humanize(snake: str) -> str:
    return snake.replace("_", " ").title()


def _enum_value(c: Any) -> str:
    if hasattr(c, "value"):
        return c.value
    return str(c)


def _scenario_corridor(name: str) -> str:
    mapping = {
        "hormuz_partial_closure": "hormuz",
        "opec_emergency_cut": "hormuz",
        "red_sea_suspension": "bab_el_mandeb",
        "australia_coking_coal": "malacca",
        "china_rare_earth_curbs": "south_china_sea",
        "china_solar_export_tariff": "south_china_sea",
        "kazakhstan_uranium_disruption": "malacca",
    }
    return mapping.get(name, "hormuz")


def _scenario_description(name: str) -> str:
    descs = {
        "hormuz_partial_closure": "50% volume reduction through Hormuz over the disruption window. Crude and Qatari LNG impacted.",
        "opec_emergency_cut": "Coordinated OPEC+ supply cut. Global crude tightens; Indian refiners exposed on spot.",
        "red_sea_suspension": "Houthi-driven full suspension of Red Sea transit. Container and LNG reroute via Cape, +18 days transit.",
        "australia_coking_coal": "Cyclone or labour action removes 30% of Queensland coking coal export volume. Indian steel margin compression.",
        "china_rare_earth_curbs": "China expands rare-earth export licensing controls. NdFeB magnet supply contracts; EV, wind, defence pinch.",
        "china_solar_export_tariff": "China retaliatory PV export tariff increase. Indian solar IRRs drop; PLI capacity insufficient short-term.",
        "kazakhstan_uranium_disruption": "Logistical or political disruption to Kazakh uranium exports. NPCIL fuel buffer ~6 months.",
    }
    return descs.get(name, f"Scenario {name}")


def _scenario_commodity(name: str) -> str:
    mapping = {
        "hormuz_partial_closure": "crude_oil",
        "opec_emergency_cut": "crude_oil",
        "red_sea_suspension": "crude_oil",
        "australia_coking_coal": "coking_coal",
        "china_rare_earth_curbs": "rare_earths",
        "china_solar_export_tariff": "solar_pv",
        "kazakhstan_uranium_disruption": "uranium",
    }
    return mapping.get(name, "crude_oil")


def _duration_factor(days: int) -> float:
    return min(1.0, (days / 14.0) ** 0.6)


def _project_impact(name: str, intensity: float, duration: int) -> dict:
    """Compute scenario impact directly from SCENARIOS params."""
    scenario = SCENARIOS[name]
    p = getattr(scenario, "params", {}) or {}
    dur = _duration_factor(duration)
    i = max(0.0, min(1.0, intensity))

    brent_uplift = 0.0
    lng_uplift = 0.0
    coal_uplift = 0.0

    if name == "hormuz_partial_closure":
        brent_uplift = 100.0 * p.get("crude_price_elasticity", 0.45) * i * p.get("crude_volume_share", 0.40)
        lng_uplift = 100.0 * p.get("lng_price_elasticity", 0.35) * i * p.get("lng_volume_share", 0.30)
    elif name == "opec_emergency_cut":
        cut = p.get("global_cut_mbd_at_full", 1.0) * i
        brent_uplift = 100.0 * p.get("crude_price_elasticity_per_mbd", 0.15) * cut
    elif name == "red_sea_suspension":
        brent_uplift = 100.0 * p.get("crude_freight_uplift_share", 0.06) * i
        lng_uplift = 100.0 * p.get("lng_uplift_share", 0.12) * i
    elif name == "australia_coking_coal":
        coal_uplift = 100.0 * p.get("coking_coal_elasticity", 0.55) * i * p.get("australia_share", 0.70)
    elif name == "china_rare_earth_curbs":
        brent_uplift = 0.0
    elif name == "china_solar_export_tariff":
        brent_uplift = 0.0
    elif name == "kazakhstan_uranium_disruption":
        brent_uplift = 0.0

    brent_uplift *= dur
    lng_uplift *= dur
    coal_uplift *= dur

    gdp_bps = -(brent_uplift * 1.5 + lng_uplift * 0.6 + coal_uplift * 0.4)
    spr_runway = max(2.0, BASE_SPR_DAYS - (brent_uplift / 10.0))
    return {
        "brent_uplift_pct": round(brent_uplift, 2),
        "lng_uplift_pct": round(lng_uplift, 2),
        "coal_uplift_pct": round(coal_uplift, 2),
        "gdp_bps": round(gdp_bps, 1),
        "spr_runway_days": round(spr_runway, 1),
    }


@router.post("/scenarios/{name}/run")
async def run_scenario_endpoint(name: str, body: dict | None = None) -> dict:
    if name not in SCENARIOS:
        raise HTTPException(status_code=404, detail=f"Unknown scenario: {name}")
    body = body or {}
    intensity = float(body.get("shockSeverity", body.get("intensity", 0.5)))
    duration = int(body.get("shockDurationDays", body.get("duration_days", 14)))

    impact = _project_impact(name, intensity, duration)
    brent_uplift_pct = impact["brent_uplift_pct"]
    lng_uplift_pct = impact["lng_uplift_pct"]
    coal_uplift_pct = impact["coal_uplift_pct"]
    gdp_bps = impact["gdp_bps"]
    spr_runway = impact["spr_runway_days"]

    fixture = _load_fixture("llm_responses.json") or {}
    narrative_key = {
        "hormuz_partial_closure": "scenario_hormuz",
        "australia_coking_coal": "scenario_australia_coal",
        "china_rare_earth_curbs": "scenario_china_rare_earth",
    }.get(name, f"scenario_{name}")
    narrative = fixture.get(narrative_key) or fixture.get("scenario_hormuz") or ""

    projected_brent = BASE_BRENT * (1 + brent_uplift_pct / 100.0)
    inflation_bps = round(gdp_bps * 0.85, 1)
    fx_impact = round(brent_uplift_pct * 0.18, 2)

    timeline = []
    for day in range(0, duration + 1, max(1, duration // 12)):
        progress = day / max(1, duration)
        ramp = min(1.0, progress * 1.4)
        timeline.append({
            "day": day,
            "brentUsd": round(BASE_BRENT + (projected_brent - BASE_BRENT) * ramp, 2),
            "sprDrawDownMb": round(0.85 * ramp, 3),
            "routeShareCape": round(0.42 * ramp, 3),
        })

    recommendations = [s.strip() for s in narrative.split(".") if s.strip()]
    if not recommendations:
        recommendations = [
            "Trigger short-cycle SPR drawdown over the first 14 days.",
            "Open dialogue with US WTI suppliers for 2 cargoes Aug-Sep.",
            "Re-route Qatari LNG via Cape window; confirm Dahej slot availability.",
        ]

    return {
        "scenarioId": name,
        "request": {
            "scenarioId": name,
            "corridor": _scenario_corridor(name),
            "commodity": _scenario_commodity(name),
            "shockDurationDays": duration,
            "shockSeverity": intensity,
            "startDate": _now_iso(),
        },
        "baseline": {
            "brentUsd": BASE_BRENT,
            "sprCoverDays": BASE_SPR_DAYS,
            "importCostUsdM": BASE_IMPORT_COST_USDM,
        },
        "projected": {
            "brentUsd": round(projected_brent, 2),
            "sprCoverDays": round(spr_runway, 1),
            "importCostUsdM": round(BASE_IMPORT_COST_USDM * (1 + brent_uplift_pct / 100.0), 1),
            "gdpImpactBps": round(gdp_bps, 1),
            "inflationImpactBps": inflation_bps,
            "fxImpactInrPerUsd": fx_impact,
        },
        "timeline": timeline,
        "recommendations": recommendations,
        "generatedAt": _now_iso(),
    }


@router.get("/digital-twin/state")
async def twin_state() -> dict:
    vessels_fixture = _load_fixture("vessels.json") or []
    vessel_count = len(vessels_fixture) if isinstance(vessels_fixture, list) else 0

    corridor_status = {
        "hormuz": "congested",
        "bab_el_mandeb": "disrupted",
        "malacca": "open",
        "south_china_sea": "congested",
        "cape_of_good_hope": "open",
        "suez": "congested",
    }
    throughput = {
        "hormuz": 19.5,
        "bab_el_mandeb": 9.2,
        "malacca": 24.1,
        "south_china_sea": 14.7,
        "cape_of_good_hope": 5.3,
        "suez": 7.8,
    }
    delays = {
        "hormuz": 6,
        "bab_el_mandeb": 26,
        "malacca": 2,
        "south_china_sea": 9,
        "cape_of_good_hope": 0,
        "suez": 4,
    }
    per_corridor_vessels = {
        "hormuz": 25,
        "bab_el_mandeb": 12,
        "malacca": 18,
        "south_china_sea": 10,
        "cape_of_good_hope": 5,
        "suez": 4,
    }

    corridors_out = []
    for corridor in ["hormuz", "bab_el_mandeb", "malacca", "south_china_sea", "cape_of_good_hope", "suez"]:
        corridors_out.append({
            "corridor": corridor,
            "throughputMbPerDay": throughput[corridor],
            "vesselCount": per_corridor_vessels[corridor],
            "averageDelayHours": delays[corridor],
            "status": corridor_status[corridor],
        })

    return {
        "asOf": _now_iso(),
        "corridors": corridors_out,
        "vessels": vessel_count or 60,
        "storage": {
            "sprFillPct": 78.5,
            "lngTerminalFillPct": 64.2,
        },
    }


@router.get("/sourcing/{commodity}")
async def sourcing(commodity: str, volumeMb: float = Query(default=100)) -> list[dict]:
    try:
        sourcing_commodity = sourcing_engine.Commodity(commodity)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Unknown commodity: {commodity}") from exc

    try:
        options = await sourcing_engine.rank_alternatives(sourcing_commodity)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    base_price = {
        "crude_oil": 82.0,
        "lng": 14.5,
        "coking_coal": 295.0,
        "lithium": 92.0,
        "cobalt": 28.0,
        "nickel": 18.0,
        "rare_earths": 540.0,
        "solar_pv": 0.105,
        "uranium": 88.0,
        "lpg": 660.0,
        "atf": 95.0,
    }.get(commodity, 100.0)

    out = []
    for opt in options[:8]:
        country = getattr(opt, "source_country", getattr(opt, "country", "Unknown"))
        rank = getattr(opt, "alternative_rank", getattr(opt, "rank", 1))
        risk = float(getattr(opt, "current_risk", 30.0))
        lead = int(getattr(opt, "lead_time_days", 28))
        rationale = getattr(opt, "rationale", "")
        share_pct = float(getattr(opt, "share_pct", 0))
        volume = round(volumeMb * (share_pct / 100.0) if share_pct else volumeMb / max(len(options), 1), 1)
        out.append({
            "rank": rank,
            "supplier": f"{country} consortium",
            "country": country,
            "commodity": commodity,
            "volumeMb": volume,
            "priceUsd": round(base_price * (1.0 + (risk - 30) / 100.0), 2),
            "leadTimeDays": lead,
            "routeCorridor": CORRIDOR_FOR_COMMODITY.get(commodity, "hormuz"),
            "routeRiskScore": round(risk, 1),
            "sanctionsCheck": "flag" if risk > 60 else "clear",
            "carbonIntensity": round(8.0 + (rank * 0.4), 2),
            "notes": rationale,
        })
    return out


def _build_spr_plan(horizon: int = 60, target_cover_days: float = 12.0, bias: str = "balanced") -> dict:
    config = spr_engine.SPRConfig(
        starting_reserve_mmb=39.0,
        max_daily_drawdown_kbpd=600.0,
        max_daily_replenish_kbpd=300.0,
        daily_consumption_kbpd=4800.0,
        supply_gap_curve=[2000.0 if d < 21 else 800.0 if d < 42 else 0.0 for d in range(horizon)],
        planning_horizon_days=horizon,
    )
    try:
        plan = spr_engine.solve_spr_plan(config)
    except Exception:
        plan = None

    today = datetime.now(timezone.utc).date()
    release_schedule = []
    sites = [
        {"name": "Visakhapatnam", "location": "Andhra Pradesh", "capacityMb": 9.77, "fillMb": 7.6, "drawRateMbPerDay": 0.25},
        {"name": "Mangalore", "location": "Karnataka", "capacityMb": 11.0, "fillMb": 8.8, "drawRateMbPerDay": 0.28},
        {"name": "Padur", "location": "Karnataka", "capacityMb": 18.3, "fillMb": 14.2, "drawRateMbPerDay": 0.42},
    ]
    total_capacity = sum(s["capacityMb"] for s in sites)
    current_fill = sum(s["fillMb"] for s in sites)

    if plan is not None:
        days_list = getattr(plan, "days", list(range(horizon)))
        drawdown_kbpd = getattr(plan, "drawdown_kbpd", [])
        cumulative = 0.0
        for i, day in enumerate(days_list[:horizon]):
            draw = float(drawdown_kbpd[i]) / 1000.0 if i < len(drawdown_kbpd) else 0.0
            cumulative += draw
            release_schedule.append({
                "day": int(day),
                "drawMb": round(draw, 3),
                "cumulativeMb": round(cumulative, 3),
                "targetMarket": "north" if bias != "south" else "south",
            })
        rationale = (
            f"LP minimises integrated price-impact over {horizon} days subject to "
            f"injection-rate, reserve, and consumption constraints. Target cover "
            f"{target_cover_days:.1f} days, bias {bias}. Solver status: "
            f"{getattr(plan, 'status', 'unknown')}."
        )
    else:
        for d in range(horizon):
            shock = 1.0 if d < 14 else 0.5 if d < 28 else 0.0
            draw = round(0.85 * shock, 3)
            cum = release_schedule[-1]["cumulativeMb"] + draw if release_schedule else draw
            release_schedule.append({
                "day": d,
                "drawMb": draw,
                "cumulativeMb": round(cum, 3),
                "targetMarket": bias,
            })
        rationale = (
            f"Heuristic schedule (LP solver unavailable). Target cover {target_cover_days:.1f} days, "
            f"bias {bias}. Switch to PuLP CBC for the full optimisation."
        )

    return {
        "asOf": _now_iso(),
        "totalCapacityMb": round(total_capacity, 2),
        "currentFillMb": round(current_fill, 2),
        "coverDays": round(BASE_SPR_DAYS, 1),
        "sites": sites,
        "releaseSchedule": release_schedule,
        "rationale": rationale,
    }


@router.get("/spr/plan")
async def get_spr_plan() -> dict:
    return _build_spr_plan()


@router.post("/spr/plan")
async def post_spr_plan(body: dict | None = None) -> dict:
    body = body or {}
    horizon = int(body.get("horizonDays", 60))
    target = float(body.get("targetCoverDays", 12.0))
    bias = str(body.get("marketBias", "balanced"))
    return _build_spr_plan(horizon=horizon, target_cover_days=target, bias=bias)


@router.get("/feed")
async def feed(limit: int = Query(default=50)) -> list[dict]:
    events = _load_fixture("gdelt_events.json") or []
    feed_items = []
    for i, e in enumerate(events[:limit]):
        feed_items.append({
            "id": str(e.get("id", i)),
            "source": "GDELT",
            "headline": e.get("actor1", "Event") + " - " + str(e.get("event_code", ""))[:64],
            "summary": f"Tone {e.get('tone', 0)}; near {e.get('location', 'unknown')}",
            "url": (e.get("urls") or [""])[0] if isinstance(e.get("urls"), list) else "",
            "publishedAt": e.get("timestamp", _now_iso()),
            "tags": [str(e.get("theme", ""))],
            "corridor": None,
            "commodity": None,
            "sentiment": "negative" if float(e.get("tone", 0)) < -3 else "neutral",
            "importance": max(1, min(10, int(abs(float(e.get("tone", 0))) * 1.2))),
        })
    return feed_items


@router.get("/executive-brief")
async def executive_brief() -> dict:
    fixture = _load_fixture("llm_responses.json") or {}
    body = fixture.get("executive_brief") or (
        "Today's snapshot: Hormuz risk elevated on US-Iran tension signals and a 4% Brent move overnight. "
        "Red Sea remains effectively closed to LNG and crude majors after this week's Houthi statements. "
        "South China Sea risk elevated on China rare-earth export licensing tightening. SPR cover stands at 9.5 days; "
        "scenario simulator shows a 5.1-day runway under a 14-day Hormuz partial closure."
    )
    return {
        "generatedAt": _now_iso(),
        "asOfDate": date.today().isoformat(),
        "headline": "Hormuz elevated; Red Sea suspended; SCS rare-earth tightening",
        "summary": body,
        "topRisks": [
            {"corridor": "hormuz", "commodity": "crude_oil", "tier": "high", "note": "GDELT + AIS anomaly"},
            {"corridor": "south_china_sea", "commodity": "rare_earths", "tier": "high", "note": "Export licensing"},
            {"corridor": "bab_el_mandeb", "commodity": "lng", "tier": "elevated", "note": "Houthi statements"},
            {"corridor": "malacca", "commodity": "coking_coal", "tier": "elevated", "note": "Queensland weather"},
        ],
        "actions": [
            "Trigger short-cycle SPR drawdown (0.85 MB/day, day 0-14).",
            "Open dialogue with US WTI suppliers for 2 cargoes Aug-Sep.",
            "Re-route Qatari LNG via Cape window; confirm Dahej slot availability.",
            "Coordinate with NPCIL on uranium contingency contracting.",
        ],
        "marketSnapshot": {
            "brentUsd": BASE_BRENT,
            "ttfEurMwh": 38.2,
            "inrUsd": 84.7,
            "coalAud": 295.4,
        },
        "citations": [
            {"label": "GDELT", "url": "https://www.gdeltproject.org"},
            {"label": "PPAC India", "url": "https://www.ppac.gov.in"},
            {"label": "EIA", "url": "https://www.eia.gov"},
        ],
    }


@router.get("/commodities")
async def commodities() -> list[dict]:
    prices = _load_fixture("commodity_prices.json") or {}
    out = []
    mapping = {
        "crude_oil": ("brent_crude_usd", "USD/bbl"),
        "lng": ("lng_jkm_usd", "USD/MMBtu"),
        "coking_coal": ("coking_coal_usd", "USD/t"),
        "lithium": ("lithium_carbonate_cny", "CNY/t"),
        "rare_earths": ("neodymium_oxide_cny", "CNY/t"),
    }
    for commodity, (fixture_key, unit) in mapping.items():
        series = prices.get(fixture_key, [])
        if isinstance(series, list) and len(series) >= 2:
            last = series[-1].get("value", 0)
            prev = series[-2].get("value", last)
            change = last - prev
            change_pct = (change / prev) * 100 if prev else 0
        else:
            last = 0
            change = 0
            change_pct = 0
        out.append({
            "commodity": commodity,
            "symbol": fixture_key,
            "priceUsd": round(float(last), 2),
            "change24h": round(float(change), 2),
            "changePct24h": round(float(change_pct), 2),
            "unit": unit,
            "asOf": _now_iso(),
        })
    return out
