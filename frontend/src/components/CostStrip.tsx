import type { CostOfInaction } from '@/lib/api';

interface CostStripProps {
  cost: CostOfInaction;
}

const SEGMENT_LABELS: Array<{ key: keyof CostOfInaction['breakdown']; label: string; color: string }> = [
  { key: 'fuelImportCost', label: 'Fuel import', color: 'bg-amber-500' },
  { key: 'gdpLoss', label: 'GDP loss', color: 'bg-red-500' },
  { key: 'refinerySpotPremium', label: 'Spot premium', color: 'bg-indigo-500' },
  { key: 'fxPassthrough', label: 'FX passthrough', color: 'bg-emerald-500' },
];

function fmtCrore(n: number): string {
  if (n >= 100000) return `₹${(n / 100000).toFixed(2)} L cr`;
  if (n >= 1000) return `₹${(n / 1000).toFixed(2)}k cr`;
  return `₹${n.toFixed(0)} cr`;
}

export function CostStrip({ cost }: CostStripProps) {
  const total = SEGMENT_LABELS.reduce((acc, s) => acc + (cost.breakdown[s.key] ?? 0), 0) || 1;

  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900 p-5">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-xs uppercase tracking-wider text-slate-400">Cost of inaction</h3>
        <span className="text-[11px] text-slate-500">{cost.durationDays} day horizon</span>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[2fr,3fr]">
        <div className="space-y-3">
          <div>
            <div className="text-[10px] uppercase tracking-wider text-slate-500">Daily</div>
            <div className="font-mono text-2xl font-semibold tabular-nums text-red-300">
              {fmtCrore(cost.dailyCostInrCrore)}
            </div>
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-wider text-slate-500">Cumulative</div>
            <div className="font-mono text-3xl font-semibold tabular-nums text-red-200">
              {fmtCrore(cost.cumulativeCostInrCrore)}
            </div>
          </div>
          <div className="text-[11px] text-slate-500">
            GDP impact {cost.gdpImpactBps >= 0 ? '+' : ''}
            {cost.gdpImpactBps.toFixed(0)} bps · India FY25 nominal GDP basis
          </div>
        </div>

        <div className="flex flex-col justify-center">
          <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-2">Breakdown</div>
          <div className="flex h-3 w-full overflow-hidden rounded-sm border border-slate-800">
            {SEGMENT_LABELS.map((seg) => {
              const value = cost.breakdown[seg.key] ?? 0;
              const pct = (value / total) * 100;
              return (
                <div
                  key={seg.key}
                  className={`${seg.color}/70 h-full`}
                  style={{ width: `${pct}%` }}
                  title={`${seg.label}: ${fmtCrore(value)} (${pct.toFixed(1)}%)`}
                />
              );
            })}
          </div>
          <div className="mt-3 grid grid-cols-2 gap-x-3 gap-y-1 text-[11px]">
            {SEGMENT_LABELS.map((seg) => {
              const value = cost.breakdown[seg.key] ?? 0;
              const pct = (value / total) * 100;
              return (
                <div key={seg.key} className="flex items-center justify-between">
                  <span className="flex items-center gap-1.5 text-slate-300">
                    <span className={`h-2 w-2 rounded-sm ${seg.color}`} />
                    {seg.label}
                  </span>
                  <span className="font-mono tabular-nums text-slate-400">{pct.toFixed(0)}%</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

export default CostStrip;
