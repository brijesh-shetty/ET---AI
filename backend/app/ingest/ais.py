"""AIS vessel tracking ingestion.

Source: AISStream.io (free realtime AIS WebSocket feed)
  - Docs: https://aisstream.io/documentation
  - Auth: API key, bbox subscription per corridor.

Provides a streaming AsyncIterator of VesselPing messages and a
synchronous-style snapshot of recently seen vessels for a corridor.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from pathlib import Path

import structlog
import websockets

from app.config import settings
from app.models import Corridor, VesselPing

log = structlog.get_logger(__name__)

_AIS_WS_URL = "wss://stream.aisstream.io/v0/stream"
_FIXTURE_PATH = Path(__file__).resolve().parents[3] / "data" / "fixtures" / "vessels.json"


async def stream_vessels(corridor: Corridor) -> AsyncIterator[VesselPing]:
    """Stream live AIS pings for vessels inside a corridor bounding box.

    Falls back to fixture replay when ALLOW_LIVE_INGEST is false or the
    AISStream API key is unset.
    """
    if not settings.allow_live_ingest or not settings.aisstream_api_key:
        async for ping in _replay_fixture(corridor):
            yield ping
        return

    bbox = _corridor_bbox(corridor)
    subscription = {
        "APIKey": settings.aisstream_api_key,
        "BoundingBoxes": [bbox],
        "FilterMessageTypes": ["PositionReport"],
    }

    try:
        async with websockets.connect(_AIS_WS_URL, ping_interval=20) as ws:
            await ws.send(json.dumps(subscription))
            log.info("ais.connected", corridor=corridor.name)
            async for raw in ws:
                msg = json.loads(raw)
                ping = _to_ping(msg, corridor)
                if ping is not None:
                    yield ping
    except (websockets.WebSocketException, OSError) as exc:
        log.warning("ais.stream_failed", error=str(exc))
        async for ping in _replay_fixture(corridor):
            yield ping


async def snapshot(corridor: Corridor) -> list[VesselPing]:
    """Return a recent snapshot of vessel pings inside the corridor.

    In live mode this drains the WebSocket briefly; otherwise it loads the
    fixture set filtered by the corridor bbox.
    """
    if not settings.allow_live_ingest or not settings.aisstream_api_key:
        return [p async for p in _replay_fixture(corridor, throttle=False)]

    pings: list[VesselPing] = []
    deadline = asyncio.get_event_loop().time() + 8.0
    async for ping in stream_vessels(corridor):
        pings.append(ping)
        if asyncio.get_event_loop().time() >= deadline or len(pings) >= 250:
            break
    return pings


def _corridor_bbox(corridor: Corridor) -> list[list[float]]:
    return [
        [corridor.bbox.south, corridor.bbox.west],
        [corridor.bbox.north, corridor.bbox.east],
    ]


def _to_ping(msg: dict, corridor: Corridor) -> VesselPing | None:
    try:
        if msg.get("MessageType") != "PositionReport":
            return None
        meta = msg.get("MetaData", {})
        pr = msg["Message"]["PositionReport"]
        return VesselPing(
            mmsi=str(pr.get("UserID") or meta.get("MMSI")),
            name=meta.get("ShipName", "").strip() or None,
            lat=float(pr["Latitude"]),
            lon=float(pr["Longitude"]),
            sog=float(pr.get("Sog", 0.0)),
            cog=float(pr.get("Cog", 0.0)),
            timestamp=meta.get("time_utc") or datetime.now(timezone.utc).isoformat(),
            corridor=corridor.name,
        )
    except (KeyError, TypeError, ValueError):
        return None


async def _replay_fixture(
    corridor: Corridor, throttle: bool = True
) -> AsyncIterator[VesselPing]:
    if not _FIXTURE_PATH.exists():
        log.warning("ais.fixture_missing", path=str(_FIXTURE_PATH))
        return

    with _FIXTURE_PATH.open("r", encoding="utf-8") as fh:
        rows = json.load(fh)

    bbox = corridor.bbox
    for row in rows:
        if not (bbox.south <= row["lat"] <= bbox.north and bbox.west <= row["lon"] <= bbox.east):
            continue
        yield VesselPing(
            mmsi=str(row["mmsi"]),
            name=row.get("name"),
            lat=float(row["lat"]),
            lon=float(row["lon"]),
            sog=float(row.get("sog", 0.0)),
            cog=float(row.get("cog", 0.0)),
            timestamp=row.get("timestamp", datetime.now(timezone.utc).isoformat()),
            corridor=corridor.name,
        )
        if throttle:
            await asyncio.sleep(0.05)
