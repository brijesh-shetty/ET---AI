import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  CircleMarker,
  MapContainer,
  Marker,
  Popup,
  TileLayer,
  Tooltip,
  useMap,
} from 'react-leaflet';
import L from 'leaflet';
import { getTwinState, type TwinState } from '@/lib/api';
import { CORRIDOR_LABEL, type Corridor } from '@/lib/types';
import { fmtNumber, fmtTime } from '@/lib/fmt';

const REFRESH_MS = 30_000;

const CORRIDOR_COORDS: Record<Corridor, { lat: number; lon: number; label: string }> = {
  hormuz: { lat: 26.5, lon: 56.2, label: 'Strait of Hormuz' },
  bab_el_mandeb: { lat: 12.6, lon: 43.4, label: 'Bab el-Mandeb' },
  malacca: { lat: 2.5, lon: 101.5, label: 'Malacca' },
  south_china_sea: { lat: 12.0, lon: 115.0, label: 'South China Sea' },
  cape_of_good_hope: { lat: -34.3, lon: 18.4, label: 'Cape of Good Hope' },
  suez: { lat: 30.0, lon: 32.5, label: 'Suez' },
};

const CORRIDOR_TO_SCENARIO: Record<Corridor, string> = {
  hormuz: 'hormuz_partial_closure',
  bab_el_mandeb: 'red_sea_suspension',
  malacca: 'australia_coking_coal',
  south_china_sea: 'china_rare_earth_curbs',
  cape_of_good_hope: 'red_sea_suspension',
  suez: 'red_sea_suspension',
};

const STATUS_FILL: Record<string, string> = {
  open: '#10b981',
  congested: '#f59e0b',
  disrupted: '#f97316',
  closed: '#ef4444',
};

const STATUS_PILL_TEXT: Record<string, string> = {
  open: 'text-emerald-300',
  congested: 'text-amber-300',
  disrupted: 'text-orange-300',
  closed: 'text-red-300',
};

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_PUBLIC_TOKEN as string | undefined;
const MAPBOX_STYLE_ID = 'mapbox/dark-v11';

function tileLayerUrl(): { url: string; attribution: string } {
  if (MAPBOX_TOKEN) {
    return {
      url: `https://api.mapbox.com/styles/v1/${MAPBOX_STYLE_ID}/tiles/{z}/{x}/{y}?access_token=${MAPBOX_TOKEN}`,
      attribution:
        '© <a href="https://www.mapbox.com/about/maps/">Mapbox</a> © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    };
  }
  return {
    url: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png',
    attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> · CARTO',
  };
}

// Fix Leaflet default icon paths in Vite builds (otherwise blank markers)
delete (L.Icon.Default.prototype as unknown as { _getIconUrl?: unknown })._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/images/marker-shadow.png',
});

function InvalidateSize({ refreshKey }: { refreshKey: number }) {
  const map = useMap();
  useEffect(() => {
    const t = setTimeout(() => map.invalidateSize(), 100);
    return () => clearTimeout(t);
  }, [map, refreshKey]);
  return null;
}

export default function DigitalTwin() {
  const navigate = useNavigate();
  const [state, setState] = useState<TwinState | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await getTwinState();
        if (cancelled) return;
        setState(data);
        setError(null);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : 'Failed to load twin state');
      }
    }
    load();
    const interval = setInterval(load, REFRESH_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  const corridors = state?.corridors ?? [];

  const tileLayer = useMemo(() => tileLayerUrl(), []);

  return (
    <div className="flex flex-col gap-4">
      <header className="flex items-end justify-between gap-4">
        <div>
          <p className="text-[11px] uppercase tracking-[0.2em] text-indigo-400">Geospatial</p>
          <h1 className="mt-1 text-xl font-semibold text-slate-100">Supply chain digital twin</h1>
          <p className="mt-1 text-xs text-slate-400">
            {MAPBOX_TOKEN ? 'Mapbox dark tiles' : 'CartoDB dark fallback'} · live vessel density,
            corridor status, Indian port linkage. Click any corridor marker to run its preset scenario.
          </p>
        </div>
        <div className="text-right text-[11px] text-slate-500">
          {state ? `Refreshed ${fmtTime(state.asOf)}` : 'Loading...'}
          {error && <div className="mt-1 text-red-400">{error}</div>}
        </div>
      </header>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr,260px]">
        <div className="overflow-hidden rounded-lg border border-slate-800 bg-slate-950 aspect-[16/9]">
          <MapContainer
            center={[18, 60]}
            zoom={3}
            scrollWheelZoom={true}
            style={{ height: '100%', width: '100%', background: '#0b0c0f' }}
            worldCopyJump={true}
          >
            <InvalidateSize refreshKey={corridors.length} />
            <TileLayer url={tileLayer.url} attribution={tileLayer.attribution} />
            {corridors.map((c) => {
              const coords = CORRIDOR_COORDS[c.corridor];
              if (!coords) return null;
              const fill = STATUS_FILL[c.status] ?? '#94a3b8';
              return (
                <CircleMarker
                  key={c.corridor}
                  center={[coords.lat, coords.lon]}
                  radius={c.status === 'closed' ? 12 : c.status === 'disrupted' ? 11 : 9}
                  pathOptions={{
                    color: fill,
                    fillColor: fill,
                    fillOpacity: 0.65,
                    weight: 2,
                  }}
                  eventHandlers={{
                    click: () => {
                      const scenario = CORRIDOR_TO_SCENARIO[c.corridor];
                      if (scenario) navigate(`/scenarios/${scenario}`);
                    },
                  }}
                >
                  <Tooltip direction="top" offset={[0, -8]} opacity={1}>
                    <span className="font-mono text-[11px]">
                      {coords.label} — {c.status}
                    </span>
                  </Tooltip>
                  <Popup>
                    <div className="font-mono text-[12px]">
                      <div className="font-semibold">{coords.label}</div>
                      <div>Status: {c.status}</div>
                      <div>Throughput: {fmtNumber(c.throughputMbPerDay, 1)} Mb/d</div>
                      <div>Vessels: {c.vesselCount}</div>
                      <div>Avg delay: {c.averageDelayHours} h</div>
                    </div>
                  </Popup>
                </CircleMarker>
              );
            })}
          </MapContainer>
        </div>

        <aside className="flex flex-col gap-3">
          <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
            <div className="text-[10px] uppercase tracking-wider text-slate-500">Vessels tracked</div>
            <div className="mt-1 text-2xl font-semibold tabular-nums text-slate-100">
              {state ? state.vessels : '--'}
            </div>
          </div>
          <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
            <div className="text-[10px] uppercase tracking-wider text-slate-500">SPR fill</div>
            <div className="mt-1 text-2xl font-semibold tabular-nums text-slate-100">
              {state ? `${fmtNumber(state.storage.sprFillPct, 0)}%` : '--'}
            </div>
            <div className="mt-1 text-[10px] text-slate-500">
              LNG terminals: {state ? `${fmtNumber(state.storage.lngTerminalFillPct, 0)}%` : '--'}
            </div>
          </div>
          <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
            <div className="mb-2 text-[10px] uppercase tracking-wider text-slate-500">Corridors</div>
            <ul className="space-y-1.5">
              {corridors.map((c) => (
                <li
                  key={c.corridor}
                  className="flex cursor-pointer items-center justify-between rounded px-1 py-0.5 text-xs text-slate-300 hover:bg-slate-800/60"
                  onClick={() => {
                    const scenario = CORRIDOR_TO_SCENARIO[c.corridor];
                    if (scenario) navigate(`/scenarios/${scenario}`);
                  }}
                >
                  <span className="flex items-center gap-1.5">
                    <span
                      className="h-1.5 w-1.5 rounded-full"
                      style={{ background: STATUS_FILL[c.status] ?? '#94a3b8' }}
                    />
                    {CORRIDOR_LABEL[c.corridor] ?? c.corridor}
                  </span>
                  <span className="flex items-center gap-1.5 tabular-nums text-slate-500">
                    <span className={`font-mono text-[10px] uppercase ${STATUS_PILL_TEXT[c.status] ?? ''}`}>
                      {c.status}
                    </span>
                    <span>{c.vesselCount}</span>
                  </span>
                </li>
              ))}
            </ul>
          </div>
          <div className="rounded-lg border border-slate-800 bg-slate-900 p-3">
            <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1.5">Legend</div>
            <div className="flex flex-wrap gap-2 text-[11px]">
              {Object.entries(STATUS_FILL).map(([k, v]) => (
                <div key={k} className="flex items-center gap-1">
                  <span className="h-1.5 w-1.5 rounded-full" style={{ background: v }} />
                  <span className="text-slate-400">{k}</span>
                </div>
              ))}
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}

void Marker;
