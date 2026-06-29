import { useEffect, useMemo, useState } from 'react';
import {
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';
import { getSourcing } from '@/lib/api';
import {
  COMMODITY_LABEL,
  type Commodity,
  type SourcingOption,
} from '@/lib/types';
import { fmtNumber } from '@/lib/fmt';
import CommodityBadge from '@/components/CommodityBadge';

const COMMODITIES: Commodity[] = [
  'crude_oil',
  'lng',
  'coking_coal',
  'lithium',
  'cobalt',
  'nickel',
  'rare_earths',
  'solar_pv',
  'uranium',
];

const PIE_COLORS = [
  '#6366f1',
  '#f97316',
  '#10b981',
  '#0ea5e9',
  '#a855f7',
  '#fbbf24',
  '#ef4444',
  '#84cc16',
  '#f43f5e',
  '#94a3b8',
];

const DEFAULT_VOLUME = 100;

export default function Sourcing() {
  const [commodity, setCommodity] = useState<Commodity>('crude_oil');
  const [options, setOptions] = useState<SourcingOption[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    async function load() {
      try {
        const data = await getSourcing(commodity, DEFAULT_VOLUME);
        if (cancelled) return;
        setOptions(data);
        setError(null);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : 'Failed to load sourcing');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [commodity]);

  const shareByCountry = useMemo(() => {
    const map = new Map<string, number>();
    options.forEach((o) => map.set(o.country, (map.get(o.country) ?? 0) + o.volumeMb));
    return Array.from(map.entries()).map(([country, volume]) => ({ country, volume }));
  }, [options]);

  const recommendation = useMemo(() => {
    if (options.length === 0) return null;
    const top = options[0];
    const cleared = options.filter((o) => o.sanctionsCheck === 'clear').length;
    return `Top alternative: ${top.supplier} in ${top.country}. ${cleared} of ${options.length} options pass sanctions check. Composite risk ${top.routeRiskScore.toFixed(0)} on the ${top.routeCorridor.replace(/_/g, ' ')} corridor.`;
  }, [options]);

  return (
    <div className="flex flex-col gap-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-[11px] uppercase tracking-[0.2em] text-indigo-400">Procurement</p>
          <h1 className="mt-1 text-xl font-semibold text-slate-100">Sourcing intelligence</h1>
          <p className="mt-1 text-xs text-slate-400">
            Ranks alternative suppliers by current risk + historical share + lead-time. Does NOT validate refinery / smelter chemistry.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-[11px] uppercase tracking-wider text-slate-500">Commodity</label>
          <select
            value={commodity}
            onChange={(e) => setCommodity(e.target.value as Commodity)}
            className="rounded-md border border-slate-700 bg-slate-900 px-2 py-1.5 text-sm text-slate-200 focus:border-indigo-500 focus:outline-none"
          >
            {COMMODITIES.map((c) => (
              <option key={c} value={c}>
                {COMMODITY_LABEL[c]}
              </option>
            ))}
          </select>
        </div>
      </header>

      {recommendation && (
        <div className="rounded-lg border border-indigo-500/30 bg-indigo-500/10 px-4 py-3 text-sm text-indigo-200">
          {recommendation}
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-red-500/40 bg-red-500/10 p-4 text-sm text-red-300">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[280px,1fr]">
        <section className="rounded-lg border border-slate-800 bg-slate-900 p-4">
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
            Suggested mix
          </h3>
          <div className="h-56 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Tooltip
                  contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: 8, fontSize: 12 }}
                />
                <Pie
                  data={shareByCountry}
                  dataKey="volume"
                  nameKey="country"
                  innerRadius={48}
                  outerRadius={84}
                  paddingAngle={2}
                  strokeWidth={0}
                >
                  {shareByCountry.map((_, i) => (
                    <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                  ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
          </div>
          <ul className="mt-2 space-y-1 text-xs">
            {shareByCountry.map((s, i) => (
              <li key={s.country} className="flex items-center justify-between">
                <span className="flex items-center gap-1.5 text-slate-300">
                  <span className="h-2 w-2 rounded-sm" style={{ background: PIE_COLORS[i % PIE_COLORS.length] }} />
                  {s.country}
                </span>
                <span className="tabular-nums text-slate-500">{fmtNumber(s.volume, 1)} MB</span>
              </li>
            ))}
          </ul>
        </section>

        <section className="rounded-lg border border-slate-800 bg-slate-900">
          <div className="flex items-center justify-between border-b border-slate-800 px-5 py-3">
            <h3 className="text-sm font-semibold text-slate-100">
              {COMMODITY_LABEL[commodity]} ranked alternatives
            </h3>
            <CommodityBadge commodity={commodity} size="md" />
          </div>
          {loading && (
            <div className="px-5 py-8 text-center text-sm text-slate-500">Loading...</div>
          )}
          {!loading && options.length === 0 && (
            <div className="px-5 py-8 text-center text-sm text-slate-500">
              No alternative sources found for this commodity.
            </div>
          )}
          {!loading && options.length > 0 && (
            <table className="w-full text-sm">
              <thead className="bg-slate-900/50 text-[10px] uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="px-4 py-2 text-left">#</th>
                  <th className="px-4 py-2 text-left">Supplier / country</th>
                  <th className="px-4 py-2 text-right">Vol MB</th>
                  <th className="px-4 py-2 text-right">Price USD</th>
                  <th className="px-4 py-2 text-right">Lead time</th>
                  <th className="px-4 py-2 text-left">Corridor</th>
                  <th className="px-4 py-2 text-right">Risk</th>
                  <th className="px-4 py-2 text-left">Sanctions</th>
                </tr>
              </thead>
              <tbody>
                {options.map((o) => (
                  <tr key={`${o.supplier}-${o.country}-${o.rank}`} className="border-t border-slate-800">
                    <td className="px-4 py-2 text-slate-300 tabular-nums">{o.rank}</td>
                    <td className="px-4 py-2">
                      <div className="text-slate-200">{o.supplier}</div>
                      <div className="text-[11px] text-slate-500">{o.country}</div>
                    </td>
                    <td className="px-4 py-2 text-right tabular-nums text-slate-300">
                      {fmtNumber(o.volumeMb, 1)}
                    </td>
                    <td className="px-4 py-2 text-right tabular-nums text-slate-300">
                      ${o.priceUsd.toFixed(2)}
                    </td>
                    <td className="px-4 py-2 text-right tabular-nums text-slate-300">{o.leadTimeDays} d</td>
                    <td className="px-4 py-2 text-xs text-slate-400">{o.routeCorridor.replace(/_/g, ' ')}</td>
                    <td className="px-4 py-2 text-right tabular-nums text-slate-300">
                      {o.routeRiskScore.toFixed(0)}
                    </td>
                    <td className="px-4 py-2">
                      <span
                        className={
                          o.sanctionsCheck === 'clear'
                            ? 'text-emerald-300'
                            : o.sanctionsCheck === 'flag'
                              ? 'text-amber-300'
                              : 'text-red-300'
                        }
                      >
                        {o.sanctionsCheck}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <div className="border-t border-slate-800 px-5 py-2 text-[11px] text-slate-500">
            Scoping note: ranks suppliers without crude grade / coal washability / lithium chemistry validation.
          </div>
        </section>
      </div>
    </div>
  );
}
