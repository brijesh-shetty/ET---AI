"""Solar PV module imports and domestic capacity tracking.

Sources:
  - MNRE (Ministry of New & Renewable Energy): https://mnre.gov.in
  - PLI Scheme (High-Efficiency Solar PV Modules) — phase I & II tranche reports.
  - DGCI&S import classification HS 8541.42/8541.43 for cells and modules.
  - Mercom India Solar Market Update.

India imports ~80% of solar modules and ~60% of cells, with China dominant.
"""

from __future__ import annotations

import json
from pathlib import Path

import structlog

from app.config import get_settings

settings = get_settings()

log = structlog.get_logger(__name__)

_FIXTURE_PATH = Path(__file__).resolve().parents[2] / "data" / "fixtures" / "solar.json"


async def module_import_shares() -> dict[str, float]:
    """Return solar module import shares by country of origin (percent)."""
    data = _load_fixture()
    shares = {k: float(v) for k, v in data.get("module_import_shares", {}).items()}
    return _normalize(shares)


async def domestic_capacity_status() -> dict:
    """Return domestic PV manufacturing status and PLI scheme progress.

    Shape:
        {
          "cell_capacity_gw": 8.1,
          "module_capacity_gw": 64.5,
          "wafer_capacity_gw": 2.0,
          "pli_tranches": [
            {"tranche": 1, "awarded_gw": 8.7, "commissioned_gw": 3.4, "awardees": [...]},
            {"tranche": 2, "awarded_gw": 39.6, "commissioned_gw": 12.8, "awardees": [...]}
          ],
          "alm_listed_companies": int,
          "import_share_module_pct": 80.0,
          "import_share_cell_pct": 60.0
        }
    """
    data = _load_fixture()
    return data.get("domestic_capacity", {})


def _normalize(shares: dict[str, float]) -> dict[str, float]:
    total = sum(shares.values()) or 1.0
    return {k: round(v * 100.0 / total, 2) for k, v in shares.items()}


def _load_fixture() -> dict:
    if not _FIXTURE_PATH.exists():
        log.warning("solar.fixture_missing", path=str(_FIXTURE_PATH))
        return {}
    if not settings.allow_live_ingest:
        log.info("solar.fixture_mode")
    with _FIXTURE_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)
