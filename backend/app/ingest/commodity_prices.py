"""Commodity price series ingestion.

Sources:
  - U.S. EIA open data (crude oil WTI/Brent, Henry Hub LNG):
      https://api.eia.gov/v2/
  - Alpha Vantage commodities: https://www.alphavantage.co/documentation/#commodity
  - World Bank Pink Sheet monthly (coal, minerals):
      https://www.worldbank.org/en/research/commodity-markets

Returns a daily series of price dicts: {date, price, unit, source}.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

import httpx
import structlog
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import settings
from app.models import Commodity

log = structlog.get_logger(__name__)

_EIA_BASE = "https://api.eia.gov/v2"
_FIXTURE_PATH = Path(__file__).resolve().parents[3] / "data" / "fixtures" / "commodity_prices.json"
_DEFAULT_TIMEOUT = httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0)

_EIA_SERIES = {
    Commodity.CRUDE: ("petroleum/pri/spt/data/", "RBRTE", "USD/bbl"),
    Commodity.LNG: ("natural-gas/pri/fut/data/", "RNGWHHD", "USD/MMBtu"),
}


async def fetch_prices(commodity: Commodity, days: int = 30) -> list[dict]:
    """Return a daily price series for the given commodity over `days`."""
    if not settings.allow_live_ingest:
        log.info("prices.fixture_mode", commodity=commodity.value, days=days)
        return _load_fixture(commodity, days)

    if commodity in _EIA_SERIES and settings.eia_api_key:
        try:
            return await _fetch_eia(commodity, days)
        except httpx.HTTPError as exc:
            log.warning("prices.eia_failed", commodity=commodity.value, error=str(exc))

    return _load_fixture(commodity, days)


async def _fetch_eia(commodity: Commodity, days: int) -> list[dict]:
    path, series_id, unit = _EIA_SERIES[commodity]
    start = (date.today() - timedelta(days=days)).isoformat()
    params = {
        "api_key": settings.eia_api_key,
        "frequency": "daily",
        "data[0]": "value",
        "facets[series][]": series_id,
        "start": start,
        "sort[0][column]": "period",
        "sort[0][direction]": "asc",
        "length": str(days + 5),
    }

    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=8),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
        reraise=True,
    ):
        with attempt:
            async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
                resp = await client.get(f"{_EIA_BASE}/{path}", params=params)
                resp.raise_for_status()
                payload = resp.json()

    rows = payload.get("response", {}).get("data", [])
    return [
        {
            "date": r["period"],
            "price": float(r["value"]),
            "unit": unit,
            "source": "EIA",
        }
        for r in rows
        if r.get("value") is not None
    ]


def _load_fixture(commodity: Commodity, days: int) -> list[dict]:
    if not _FIXTURE_PATH.exists():
        log.warning("prices.fixture_missing", path=str(_FIXTURE_PATH))
        return []
    with _FIXTURE_PATH.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    series = data.get(commodity.value, [])
    cutoff = date.today() - timedelta(days=days)
    out: list[dict] = []
    for row in series:
        try:
            d = datetime.fromisoformat(row["date"]).date()
        except (KeyError, ValueError):
            continue
        if d < cutoff:
            continue
        out.append(row)
    return out
