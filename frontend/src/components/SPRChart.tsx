import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { SPRPlan } from '@/lib/types';

interface SPRChartProps {
  plan: SPRPlan;
  baseline?: SPRPlan;
}

interface ChartRow {
  day: number;
  optimisedDraw: number;
  optimisedCumulative: number;
  baselineDraw?: number;
  baselineCumulative?: number;
}

function toRows(plan: SPRPlan): ChartRow[] {
  return plan.releaseSchedule.map((r) => ({
    day: r.day,
    optimisedDraw: r.drawMb,
    optimisedCumulative: r.cumulativeMb,
  }));
}

function merge(rows: ChartRow[], baseline: SPRPlan | undefined): ChartRow[] {
  if (!baseline) return rows;
  const map = new Map<number, ChartRow>();
  rows.forEach((r) => map.set(r.day, { ...r }));
  baseline.releaseSchedule.forEach((r) => {
    const existing = map.get(r.day);
    if (existing) {
      existing.baselineDraw = r.drawMb;
      existing.baselineCumulative = r.cumulativeMb;
    } else {
      map.set(r.day, {
        day: r.day,
        optimisedDraw: 0,
        optimisedCumulative: 0,
        baselineDraw: r.drawMb,
        baselineCumulative: r.cumulativeMb,
      });
    }
  });
  return Array.from(map.values()).sort((a, b) => a.day - b.day);
}

export function SPRChart({ plan, baseline }: SPRChartProps) {
  const rows = merge(toRows(plan), baseline);
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-100">SPR drawdown vs baseline</h3>
        <div className="text-xs text-slate-500">
          {plan.currentFillMb.toFixed(1)} MB current fill
        </div>
      </div>
      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={rows} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="#1e293b" strokeDasharray="3 3" />
            <XAxis
              dataKey="day"
              stroke="#64748b"
              tick={{ fill: '#94a3b8', fontSize: 11 }}
              label={{ value: 'Day', position: 'insideBottom', offset: -2, fill: '#64748b', fontSize: 11 }}
            />
            <YAxis stroke="#64748b" tick={{ fill: '#94a3b8', fontSize: 11 }} />
            <Tooltip
              contentStyle={{
                background: '#0f172a',
                border: '1px solid #334155',
                borderRadius: 8,
                fontSize: 12,
              }}
              labelStyle={{ color: '#94a3b8' }}
            />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Area
              type="monotone"
              dataKey="optimisedDraw"
              name="Optimised daily draw (MB)"
              fill="#6366f1"
              fillOpacity={0.25}
              stroke="#6366f1"
              strokeWidth={2}
            />
            {baseline && (
              <Area
                type="monotone"
                dataKey="baselineDraw"
                name="Baseline daily draw (MB)"
                fill="#f97316"
                fillOpacity={0.15}
                stroke="#f97316"
                strokeWidth={1.5}
                strokeDasharray="4 3"
              />
            )}
            <Line
              type="monotone"
              dataKey="optimisedCumulative"
              name="Cumulative drawn (MB)"
              stroke="#a5b4fc"
              strokeWidth={2}
              dot={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export default SPRChart;
