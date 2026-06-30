"""VEDAS (ISRO Space Applications Centre) infrastructure layers.

Surfaces the Indian energy distribution network — major crude/product
pipelines and natural-gas trunk lines — as polylines suitable for the
digital-twin map.

Live source: VEDAS API Centre (vedas.sac.gov.in/vconsole). Registered users
get an API key tied to specific dataset access. The endpoint URL pattern and
auth header are NOT publicly documented; the user provides them via:
    settings.vedas_api_key  (env: VEDAS_API_KEY)
    settings.vedas_base_url (env: VEDAS_BASE_URL, default https://vedas.sac.gov.in)

Until the live endpoint is wired (see _LAYER_PATHS below), the module returns
a fixture of major Indian pipelines compiled from public PNGRB/MoPNG/GAIL
infrastructure maps. This gives the demo a credible Indian distribution
network out of the box; the live VEDAS call replaces it when configured.

Strict graceful degradation: any failure falls back to fixture data."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import httpx
import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)
_settings = get_settings()

_FIXTURE_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "fixtures" / "pipelines.json"
)
_TIMEOUT = httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0)

# Placeholder VEDAS layer paths — filled in by the user once they share their
# console-issued endpoint structure. Keys here MUST match the dict keys the
# /api/digital-twin/state endpoint expects ("oilPipelines", "gasPipelines").
# When the URL pattern is known, set e.g.:
#     "oilPipelines": "/api/v1/layers/oil_pipelines/geojson"
# along with the header/query the key is passed in.
_LAYER_PATHS: dict[str, Optional[str]] = {
    "oilPipelines": None,   # e.g. "/api/v1/layers/india_crude_pipelines.geojson"
    "gasPipelines": None,   # e.g. "/api/v1/layers/india_gas_pipelines.geojson"
}


def _load_fixture() -> dict[str, Any]:
    if not _FIXTURE_PATH.exists():
        log.warning("vedas.fixture_missing", path=str(_FIXTURE_PATH))
        return {"oil": [], "gas": []}
    with _FIXTURE_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def fixture_pipelines() -> tuple[list[dict], list[dict]]:
    """Return (oil, gas) pipeline lists from the bundled fixture."""
    data = _load_fixture()
    return list(data.get("oil") or []), list(data.get("gas") or [])


def _normalise_feature(feature: dict, layer_kind: str) -> Optional[dict]:
    """Best-effort GeoJSON → internal pipeline shape. Accepts a Feature with a
    LineString or MultiLineString geometry; pulls common property names that
    VEDAS-style layers tend to expose. Returns None on shape mismatch."""
    geom = (feature or {}).get("geometry") or {}
    gtype = geom.get("type")
    props = (feature or {}).get("properties") or {}

    coords: list[list[float]] = []
    if gtype == "LineString":
        coords = list(geom.get("coordinates") or [])
    elif gtype == "MultiLineString":
        for line in geom.get("coordinates") or []:
            coords.extend(list(line))
    else:
        return None

    polyline = []
    for c in coords:
        if isinstance(c, (list, tuple)) and len(c) >= 2:
            lon, lat = float(c[0]), float(c[1])
            polyline.append({"lat": lat, "lon": lon})
    if not polyline:
        return None

    return {
        "id": str(props.get("id") or props.get("ogc_fid") or props.get("name") or f"vedas_{layer_kind}_{len(polyline)}"),
        "name": props.get("name") or props.get("pipeline") or props.get("Pipeline") or "Unnamed pipeline",
        "operator": props.get("operator") or props.get("Operator") or props.get("owner") or "Unknown",
        "type": props.get("type") or ("crude" if layer_kind == "oil" else None),
        "lengthKm": props.get("length_km") or props.get("lengthKm") or None,
        "throughputMtpa": props.get("throughput_mtpa") or props.get("throughputMtpa") or None,
        "capacityMmscmd": props.get("capacity_mmscmd") or props.get("capacityMmscmd") or None,
        "polyline": polyline,
    }


async def _fetch_layer(layer_kind: str) -> Optional[list[dict]]:
    """Make the live VEDAS call for one layer. Returns None if VEDAS is not
    configured (key/path missing) so the caller can fall back to fixture."""
    path = _LAYER_PATHS.get(layer_kind)
    if not path or not _settings.vedas_api_key:
        return None
    url = f"{_settings.vedas_base_url.rstrip('/')}{path}"
    # Auth: pass the key both as a Bearer header AND a query param to cover the
    # two common VEDAS patterns. Whichever the server actually checks will work;
    # the other is ignored. Update once we know the canonical method.
    headers = {"Authorization": f"Bearer {_settings.vedas_api_key}"}
    params = {"key": _settings.vedas_api_key}
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            r = await client.get(url, headers=headers, params=params)
            r.raise_for_status()
            payload = r.json()
    except Exception as exc:
        log.warning("vedas.fetch_failed", layer=layer_kind, error=str(exc))
        return None

    # Accept either a raw FeatureCollection or a {features: [...]} envelope.
    features = payload.get("features") if isinstance(payload, dict) else None
    if features is None:
        log.info("vedas.unexpected_shape", layer=layer_kind, keys=list(payload.keys()) if isinstance(payload, dict) else type(payload).__name__)
        return None

    out: list[dict] = []
    for f in features:
        norm = _normalise_feature(f, layer_kind)
        if norm:
            out.append(norm)
    log.info("vedas.fetched", layer=layer_kind, count=len(out))
    return out


async def fetch_pipelines() -> dict[str, list[dict]]:
    """Return {oilPipelines, gasPipelines}. Live VEDAS data when configured;
    fixture otherwise. Per-layer graceful fallback — if oil succeeds and gas
    fails, you get live oil + fixture gas."""
    oil_fixture, gas_fixture = fixture_pipelines()

    if not _settings.allow_live_ingest:
        return {"oilPipelines": oil_fixture, "gasPipelines": gas_fixture}

    live_oil = await _fetch_layer("oilPipelines")
    live_gas = await _fetch_layer("gasPipelines")

    return {
        "oilPipelines": live_oil if live_oil else oil_fixture,
        "gasPipelines": live_gas if live_gas else gas_fixture,
    }
