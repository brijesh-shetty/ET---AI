"""Critical mineral source concentration.

Sources:
  - USGS Mineral Commodity Summaries: https://www.usgs.gov/centers/national-minerals-information-center/mineral-commodity-summaries
  - IEA Critical Minerals Market Review: https://www.iea.org/reports/critical-minerals-market-review-2024
  - Ministry of Mines (India), KABIL, IREL disclosures.
  - BloombergNEF Lithium-Ion Battery Supply Chain rankings.

Covers lithium, cobalt, nickel, rare earth elements (REE). Reports the
Herfindahl-style refining concentration index and a flag where China dominates
processing (>50% global refining share).
"""

from __future__ import annotations

import json
from pathlib import Path

import structlog

from app.config import settings
from app.models import Commodity

log = structlog.get_logger(__name__)

_FIXTURE_PATH = Path(__file__).resolve().parents[3] / "data" / "fixtures" / "minerals.json"

_CHINA_REFINING_SHARE = {
    Commodity.LITHIUM: 0.65,
    Commodity.COBALT: 0.74,
    Commodity.NICKEL: 0.28,
    Commodity.RARE_EARTH: 0.90,
}


async def critical_mineral_sources() -> dict[Commodity, dict[str, float]]:
    """Return per-mineral source country shares and concentration metrics.

    Shape:
        {
          Commodity.LITHIUM: {
            "mining": {"Australia": 0.47, "Chile": 0.30, ...},
            "refining": {"China": 0.65, "Chile": 0.29, ...},
            "hhi_refining": 0.49,
            "china_dominant": true
          },
          ...
        }
    """
    raw = _load_fixture()
    out: dict[Commodity, dict[str, float]] = {}
    for c in (Commodity.LITHIUM, Commodity.COBALT, Commodity.NICKEL, Commodity.RARE_EARTH):
        entry = raw.get(c.value, {})
        mining = {k: float(v) for k, v in entry.get("mining", {}).items()}
        refining = {k: float(v) for k, v in entry.get("refining", {}).items()}
        hhi = _hhi(refining)
        china_share = refining.get("China", _CHINA_REFINING_SHARE.get(c, 0.0))
        out[c] = {
            "mining": mining,
            "refining": refining,
            "hhi_refining": round(hhi, 3),
            "china_share_refining": round(china_share, 3),
            "china_dominant": china_share >= 0.5,
        }
    return out


def _hhi(shares: dict[str, float]) -> float:
    total = sum(shares.values()) or 1.0
    return sum((v / total) ** 2 for v in shares.values())


def _load_fixture() -> dict:
    if not _FIXTURE_PATH.exists():
        log.warning("minerals.fixture_missing", path=str(_FIXTURE_PATH))
        return {}
    if not settings.allow_live_ingest:
        log.info("minerals.fixture_mode")
    with _FIXTURE_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)
