"""Best-effort scraper for Indian retail pump prices (petrol, diesel, LPG, CNG).

Why this exists: there's no free machine-readable API for Indian retail fuel
prices. PPAC publishes daily PDFs; OMCs (IOCL/HPCL/BPCL) only display today's
price on their websites with no documented endpoint. This module scrapes
goodreturns.in's sidebar widget — a structured fragment present on every fuel
page that gives the four current Indian retail fuel prices in clean HTML.

Strict graceful degradation: any failure (network, parse, site redesign) leaves
the documented snapshot in place. The caller never sees an exception."""
from __future__ import annotations

import asyncio
import re
import time
from typing import Optional

import httpx
import structlog

log = structlog.get_logger(__name__)

# Spoof a real browser UA — python-httpx's default UA gets 403'd by some CDNs.
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# All four fuels co-occur in the page sidebar; one fetch gets the lot.
_LANDING_URL = "https://www.goodreturns.in/petrol-price.html"

# Sidebar widget marks each fuel with <span class="label">NAME</span> and
# the value in the next <span class="value">₹ NN.NN</span>. The widget is
# tight (no newlines between the two spans on the rendered page), so a small
# lookahead window is enough.
_RUPEE = "₹"
_FUELS = ("Petrol", "Diesel", "LPG", "CNG")
_VALUE_WINDOW = 220  # chars to look forward from the label for a price

# Module-level cache so a startup refresh + ad-hoc /api/baselines call don't
# both hit the upstream within the same hour.
_CACHE: dict[str, float | float | None] = {"value": None, "fetched_at": 0.0}
_CACHE_TTL_SECONDS = 3600  # 1 hour


def _extract_price_after_label(body: str, label: str) -> Optional[float]:
    """Find the first plausible Indian-pump price within a short window after
    the labelled span. Returns None if not found or out of range."""
    pattern_label = re.compile(rf'class="label">\s*{label}\s*</span>', re.I)
    m = pattern_label.search(body)
    if not m:
        return None
    window = body[m.end() : m.end() + _VALUE_WINDOW]
    value_pat = re.compile(
        rf'class="value">\s*(?:{re.escape(_RUPEE)}|Rs\.?)?\s*([0-9]{{2,4}}\.[0-9]{{1,2}})',
        re.I,
    )
    vm = value_pat.search(window)
    if not vm:
        return None
    try:
        val = float(vm.group(1))
    except ValueError:
        return None
    # Plausible Indian-pump range across all four fuels (LPG can reach ~1000/cyl).
    if not (40.0 < val < 1500.0):
        return None
    return val


async def fetch_indian_pump_prices() -> dict[str, float]:
    """Return {petrol, diesel, lpg, cng} in Indian retail units (Rs/L for the
    first three, Rs/kg for CNG). Missing keys mean the scrape failed for that
    fuel; the caller should keep its existing snapshot for those."""
    now = time.time()
    cached = _CACHE.get("value")
    if cached and (now - float(_CACHE.get("fetched_at") or 0.0)) < _CACHE_TTL_SECONDS:
        return cached  # type: ignore[return-value]

    try:
        async with httpx.AsyncClient(
            timeout=10.0, follow_redirects=True, headers={"User-Agent": _UA}
        ) as client:
            r = await client.get(_LANDING_URL)
            r.raise_for_status()
            body = r.text
    except Exception as exc:
        log.warning("pump_prices.fetch_failed", error=str(exc))
        return {}

    out: dict[str, float] = {}
    for label in _FUELS:
        val = _extract_price_after_label(body, label)
        if val is not None:
            out[label.lower()] = val

    if out:
        _CACHE["value"] = out  # type: ignore[assignment]
        _CACHE["fetched_at"] = now
        log.info("pump_prices.scraped", **out)
    else:
        log.warning("pump_prices.parse_failed", body_bytes=len(body))
    return out


# Convenience for the baselines refresh path.
async def fetch_diesel_inr_per_l() -> Optional[float]:
    prices = await fetch_indian_pump_prices()
    return prices.get("diesel")
