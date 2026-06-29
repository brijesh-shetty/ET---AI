import { useEffect, useState } from 'react';
import { getSPRPlan, postSPRPlan } from '@/lib/api';
import type { SPRPlan } from '@/lib/types';
import { fmtNumber, fmtTime } from '@/lib/fmt';
import SPRChart from '@/components/SPRChart';
import NarrativeFeed from '@/components/NarrativeFeed';

interface FormState {
  targetCoverDays: number;
  horizonDays: number;
  marketBias: 'north' | 'south' | 'balanced';
}

const DEFAULT_FORM: FormState = {
  targetCoverDays: 12,
  horizonDays: 60,
  marketBias: 'balanced',
};

function syntheticBaseline(plan: SPRPlan): SPRPlan {
  const releaseSchedule = plan.releaseSchedule.map((r, i) => {
    const flat = plan.releaseSchedule.length > 0
      ? plan.releaseSchedule.reduce((a, b) => a + b.drawMb, 0) / plan.releaseSchedule.length
      : 0;
    return {
      day: r.day,
      drawMb: flat,
      cumulativeMb: flat * (i + 1),
      targetMarket: 'flat baseline',
    };
  });
  return { ...plan, releaseSchedule, rationale: 'Constant-rate baseline (no optimisation).' };
}

export default function SPR() {
  const [plan, setPlan] = useState<SPRPlan | null>(null);
  const [baseline, setBaseline] = useState<SPRPlan | null>(null);
  const [form, setForm] = useState<FormState>(DEFAULT_FORM);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const p = await getSPRPlan();
        if (cancelled) return;
        setPlan(p);
        setBaseline(syntheticBaseline(p));
        setError(null);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : 'Failed to load SPR plan');
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  async function solve() {
    setLoading(true);
    try {
      const p = await postSPRPlan({
        targetCoverDays: form.targetCoverDays,
        horizonDays: form.horizonDays,
        marketBias: form.marketBias,
      });
      setPlan(p);
      setBaseline(syntheticBaseline(p));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to solve SPR plan');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-[11px] uppercase tracking-[0.2em] text-indigo-400">Strategic reserves</p>
          <h1 className="mt-1 text-xl font-semibold text-slate-100">SPR drawdown optimiser</h1>
          <p className="mt-1 text-xs text-slate-400">
            Linear program minimises price-impact over a planning horizon subject to reserve, injection and consumption constraints.
          </p>
        </div>
        {plan && (
          <div className="text-right text-[11px] text-slate-500">
            Plan as of {fmtTime(plan.asOf)}
          </div>
        )}
      </header>

      <section className="grid grid-cols-1 gap-3 sm:grid-cols-4">
        <div className="rounded-lg border border-slate-800 bg-slate-900 p-3">
          <label className="text-[10px] uppercase tracking-wider text-slate-500">Target cover (days)</label>
          <input
            type="number"
            min={5}
            max={30}
            step={1}
            value={form.targetCoverDays}
            onChange={(e) =>
              setForm({ ...form, targetCoverDays: Number(e.target.value) || DEFAULT_FORM.targetCoverDays })
            }
            className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-2 py-1 text-sm tabular-nums text-slate-100"
          />
        </div>
        <div className="rounded-lg border border-slate-800 bg-slate-900 p-3">
          <label className="text-[10px] uppercase tracking-wider text-slate-500">Horizon (days)</label>
          <input
            type="number"
            min={14}
            max={180}
            step={1}
            value={form.horizonDays}
            onChange={(e) =>
              setForm({ ...form, horizonDays: Number(e.target.value) || DEFAULT_FORM.horizonDays })
            }
            className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-2 py-1 text-sm tabular-nums text-slate-100"
          />
        </div>
        <div className="rounded-lg border border-slate-800 bg-slate-900 p-3">
          <label className="text-[10px] uppercase tracking-wider text-slate-500">Market bias</label>
          <select
            value={form.marketBias}
            onChange={(e) => setForm({ ...form, marketBias: e.target.value as FormState['marketBias'] })}
            className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-2 py-1 text-sm text-slate-100"
          >
            <option value="balanced">Balanced</option>
            <option value="north">North India</option>
            <option value="south">South India</option>
          </select>
        </div>
        <div className="flex items-end">
          <button
            type="button"
            onClick={solve}
            disabled={loading}
            className="w-full rounded-md border border-indigo-500/60 bg-indigo-500/20 px-3 py-2 text-sm font-semibold text-indigo-100 hover:bg-indigo-500/30 disabled:opacity-50"
          >
            {loading ? 'Solving...' : 'Solve plan'}
          </button>
        </div>
      </section>

      {error && (
        <div className="rounded-lg border border-red-500/40 bg-red-500/10 p-4 text-sm text-red-300">
          {error}
        </div>
      )}

      {plan && (
        <>
          <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
              <div className="text-[10px] uppercase tracking-wider text-slate-500">Total capacity</div>
              <div className="mt-1 text-2xl font-semibold tabular-nums text-slate-100">
                {fmtNumber(plan.totalCapacityMb, 1)} MB
              </div>
            </div>
            <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
              <div className="text-[10px] uppercase tracking-wider text-slate-500">Current fill</div>
              <div className="mt-1 text-2xl font-semibold tabular-nums text-slate-100">
                {fmtNumber(plan.currentFillMb, 1)} MB
              </div>
            </div>
            <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
              <div className="text-[10px] uppercase tracking-wider text-slate-500">Cover days</div>
              <div className="mt-1 text-2xl font-semibold tabular-nums text-slate-100">
                {plan.coverDays.toFixed(1)}
              </div>
            </div>
            <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
              <div className="text-[10px] uppercase tracking-wider text-slate-500">Sites</div>
              <div className="mt-1 text-2xl font-semibold tabular-nums text-slate-100">
                {plan.sites.length}
              </div>
            </div>
          </section>

          <SPRChart plan={plan} baseline={baseline ?? undefined} />

          <section className="rounded-lg border border-slate-800 bg-slate-900">
            <div className="border-b border-slate-800 px-5 py-3">
              <h3 className="text-sm font-semibold text-slate-100">Site allocation</h3>
            </div>
            <table className="w-full text-sm">
              <thead className="bg-slate-900/50 text-[10px] uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="px-4 py-2 text-left">Site</th>
                  <th className="px-4 py-2 text-left">Location</th>
                  <th className="px-4 py-2 text-right">Capacity</th>
                  <th className="px-4 py-2 text-right">Fill</th>
                  <th className="px-4 py-2 text-right">Daily draw</th>
                </tr>
              </thead>
              <tbody>
                {plan.sites.map((s) => (
                  <tr key={s.name} className="border-t border-slate-800">
                    <td className="px-4 py-2 text-slate-200">{s.name}</td>
                    <td className="px-4 py-2 text-slate-400">{s.location}</td>
                    <td className="px-4 py-2 text-right tabular-nums text-slate-300">{fmtNumber(s.capacityMb, 1)} MB</td>
                    <td className="px-4 py-2 text-right tabular-nums text-slate-300">{fmtNumber(s.fillMb, 1)} MB</td>
                    <td className="px-4 py-2 text-right tabular-nums text-slate-300">{fmtNumber(s.drawRateMbPerDay, 2)} MB/d</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <NarrativeFeed
            title="LP rationale"
            body={plan.rationale}
            generatedAt={plan.asOf}
            model="claude-opus-4-8"
          />
        </>
      )}
    </div>
  );
}
