"""LNG import shares and terminal utilization.

Sources:
  - GIIGNL Annual Report: https://giignl.org/publications/
  - PPAC Snapshot of India's Oil and Gas Data (monthly):
      https://ppac.gov.in/content/210_1_NaturalGas.aspx
  - Petronet LNG, Shell Hazira, GAIL Dabhol, Kochi LNG operator disclosures.

India's regas terminals tracked: Dahej, Hazira, Kochi, Dabhol, Ennore.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import structlog

from app.config import get_settings

settings = get_settings()

log = structlog.get_logger(__name__)

_FIXTURE_PATH = Path(__file__).resolve().parents[2] / "data" / "fixtures" / "lng.json"
_DEFAULT_TIMEOUT = httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0)
_PPAC_URL = "https://ppac.gov.in/WriteReadData/Reports/lng_imports.json"


async def import_shares() -> dict[str, float]:
    """Return LNG import shares by country of origin (percent of total volume).

    Typical India mix: Qatar (~40%), US (~20%), UAE (~10%), Australia, Nigeria,
    Russia. Percentages should sum to ~100.
    """
    if not settings.allow_live_ingest:
        return _load_fixture("import_shares")

    try:
        async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
            resp = await client.get(_PPAC_URL)
            resp.raise_for_status()
            payload = resp.json()
        shares = {row["country"]: float(row["share_pct"]) for row in payload}
        return _normalize_shares(shares)
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        log.warning("lng.shares_live_failed", error=str(exc))
        return _load_fixture("import_shares")


async def terminal_status() -> list[dict]:
    """Return per-terminal status and utilization.

    Each row: {terminal, operator, location, nameplate_mtpa, throughput_mtpa,
    utilization_pct, status}.
    """
    if not settings.allow_live_ingest:
        return _load_fixture("terminals")

    return _load_fixture("terminals")


def _normalize_shares(shares: dict[str, float]) -> dict[str, float]:
    total = sum(shares.values()) or 1.0
    return {k: round(v * 100.0 / total, 2) for k, v in shares.items()}


def _load_fixture(key: str):
    if not _FIXTURE_PATH.exists():
        log.warning("lng.fixture_missing", path=str(_FIXTURE_PATH))
        return {} if key == "import_shares" else []
    with _FIXTURE_PATH.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    return data.get(key, {} if key == "import_shares" else [])
