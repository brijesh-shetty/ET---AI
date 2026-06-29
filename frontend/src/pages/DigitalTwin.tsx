import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
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

const STATUS_COLOR: Record<string, string> = {
  open: 'bg-emerald-500',
  congested: 'bg-amber-500',
  disrupted: 'bg-orange-500',
  closed: 'bg-red-500',
};

interface MapDotProps {
  x: number;
  y: number;
  size: number;
  color: string;
  label?: string;
  onClick?: () => void;
  ring?: boolean;
}

function MapDot({ x, y, size, color, label, onClick, ring }: MapDotProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{ left: `${x}%`, top: `${y}%`, width: size, height: size }}
      className="group absolute -translate-x-1/2 -translate-y-1/2 outline-none"
    >
      <span
        className={`block h-full w-full rounded-full ${color} ${
          ring ? 'ring-2 ring-white/30' : ''
        } shadow-lg shadow-black/40 transition-transform group-hover:scale-125`}
      />
      {label && (
        <span className="pointer-events-none absolute left-1/2 top-full mt-1 -translate-x-1/2 whitespace-nowrap rounded bg-slate-950/90 px-1.5 py-0.5 text-[10px] uppercase tracking-wider text-slate-300 opacity-0 transition-opacity group-hover:opacity-100">
          {label}
        </span>
      )}
    </button>
  );
}

function lonToX(lon: number) {
  return ((lon + 180) / 360) * 100;
}

function latToY(lat: number) {
  return ((90 - lat) / 180) * 100;
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

  const legendCorridors = useMemo(() => {
    return corridors.map((c) => ({
      corridor: c.corridor,
      label: CORRIDOR_LABEL[c.corridor] ?? c.corridor,
      status: c.status,
      vessels: c.vesselCount,
      throughput: c.throughputMbPerDay,
    }));
  }, [corridors]);

  return (
    <div className="flex flex-col gap-4">
      <header className="flex items-end justify-between gap-4">
        <div>
          <p className="text-[11px] uppercase tracking-[0.2em] text-indigo-400">Geospatial</p>
          <h1 className="mt-1 text-xl font-semibold text-slate-100">Supply chain digital twin</h1>
          <p className="mt-1 text-xs text-slate-400">
            Live vessel density, corridor status, and Indian port linkage. Click any corridor to run its preset scenario.
          </p>
        </div>
        <div className="text-right text-[11px] text-slate-500">
          {state ? `Refreshed ${fmtTime(state.asOf)}` : 'Loading...'}
          {error && <div className="mt-1 text-red-400">{error}</div>}
        </div>
      </header>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr,260px]">
        <div className="relative aspect-[16/9] overflow-hidden rounded-lg border border-slate-800 bg-slate-950">
          <div
            className="absolute inset-0"
            style={{
              backgroundImage:
                'radial-gradient(circle at 20% 30%, rgba(56,189,248,0.07), transparent 40%), radial-gradient(circle at 70% 60%, rgba(99,102,241,0.07), transparent 40%)',
            }}
          />
          <svg
            viewBox="0 0 100 56"
            preserveAspectRatio="none"
            className="pointer-events-none absolute inset-0 h-full w-full"
          >
            <defs>
              <pattern id="grid" width="5" height="5" patternUnits="userSpaceOnUse">
                <path d="M5 0 L0 0 0 5" fill="none" stroke="#1e293b" strokeWidth="0.1" />
              </pattern>
            </defs>
            <rect width="100" height="56" fill="url(#grid)" />
            <path
              d="M 14 16 Q 22 14 30 18 T 50 22 T 72 28 T 92 36"
              fill="none"
              stroke="#334155"
              strokeWidth="0.3"
              strokeDasharray="0.5,0.5"
            />
            <path
              d="M 10 20 Q 30 30 50 32 T 88 38"
              fill="none"
              stroke="#334155"
              strokeWidth="0.3"
              strokeDasharray="0.5,0.5"
            />
          </svg>

          {legendCorridors.map((c) => {
            const coords = CORRIDOR_COORDS[c.corridor];
            if (!coords) return null;
            return (
              <MapDot
                key={c.corridor}
                x={lonToX(coords.lon)}
                y={latToY(coords.lat) * (56 / 90)}
                size={c.status === 'closed' ? 22 : c.status === 'disrupted' ? 20 : 16}
                color={STATUS_COLOR[c.status] ?? 'bg-slate-500'}
                label={`${coords.label} - ${c.status}`}
                ring={c.status !== 'open'}
                onClick={() => {
                  const scenario = CORRIDOR_TO_SCENARIO[c.corridor];
                  if (scenario) navigate(`/scenarios/${scenario}`);
                }}
              />
            );
          })}

          <div className="absolute bottom-3 left-3 rounded border border-slate-800 bg-slate-950/80 px-3 py-2 text-[11px] text-slate-400 backdrop-blur">
            <div className="mb-1 font-semibold uppercase tracking-wider text-slate-300">
              Corridor status
            </div>
            <div className="flex gap-3">
              {Object.entries(STATUS_COLOR).map(([k, v]) => (
                <div key={k} className="flex items-center gap-1.5">
                  <span className={`h-2 w-2 rounded-full ${v}`} />
                  <span>{k}</span>
                </div>
              ))}
            </div>
          </div>
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
              {legendCorridors.map((c) => (
                <li
                  key={c.corridor}
                  className="flex cursor-pointer items-center justify-between rounded px-1 py-0.5 text-xs text-slate-300 hover:bg-slate-800/60"
                  onClick={() => {
                    const scenario = CORRIDOR_TO_SCENARIO[c.corridor];
                    if (scenario) navigate(`/scenarios/${scenario}`);
                  }}
                >
                  <span className="flex items-center gap-1.5">
                    <span className={`h-1.5 w-1.5 rounded-full ${STATUS_COLOR[c.status] ?? 'bg-slate-500'}`} />
                    {c.label}
                  </span>
                  <span className="tabular-nums text-slate-500">{c.vessels}</span>
                </li>
              ))}
            </ul>
          </div>
        </aside>
      </div>
    </div>
  );
}
