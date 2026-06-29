"""Coking coal import flows and steel-plant demand.

Sources:
  - Ministry of Steel: https://steel.gov.in/en/statistics
  - DGMS (Directorate General of Mine Safety) annual reports.
  - DGCI&S Foreign Trade data: https://dgciskol.gov.in
  - SteelMint India / mjunction trade flow notes.

Tracks coking coal origin mix (Australia ~70%, US, Mozambique, Russia,
Indonesia) and demand at the major integrated steel plants.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import structlog

from app.config import settings

log = structlog.get_logger(__name__)

_FIXTURE_PATH = Path(__file__).resolve().parents[3] / "data" / "fixtures" / "coal.json"
_DEFAULT_TIMEOUT = httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0)
_STEEL_MIN_URL = "https://steel.gov.in/api/coking_coal_imports.json"


async def coking_coal_imports() -> dict[str, float]:
    """Return coking coal imports by country of origin in million tonnes (annualized).

    Order of magnitude: India imports ~60 Mt/yr of coking coal.
    """
    if not settings.allow_live_ingest:
        return _load_fixture("imports_by_country")

    try:
        async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
            resp = await client.get(_STEEL_MIN_URL)
            resp.raise_for_status()
            payload = resp.json()
        return {row["country"]: float(row["mt"]) for row in payload}
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        log.warning("coal.imports_live_failed", error=str(exc))
        return _load_fixture("imports_by_country")


async def steel_plant_demand() -> list[dict]:
    """Return coking coal demand per major Indian steel plant.

    Each row: {plant, operator, location, port, crude_steel_mtpa,
    coking_coal_mtpa, import_dependency_pct}.
    Plants: SAIL Bhilai/Rourkela/Bokaro/Durgapur, Tata Jamshedpur/Kalinganagar,
    JSW Vijayanagar/Dolvi, AM/NS Hazira, RINL Vizag.
    """
    return _load_fixture("plants")


def _load_fixture(key: str):
    if not _FIXTURE_PATH.exists():
        log.warning("coal.fixture_missing", path=str(_FIXTURE_PATH))
        return {} if key == "imports_by_country" else []
    with _FIXTURE_PATH.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    return data.get(key, {} if key == "imports_by_country" else [])
