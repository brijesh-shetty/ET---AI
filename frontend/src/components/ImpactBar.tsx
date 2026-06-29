interface ImpactBarProps {
  label: string;
  value: number;
  max: number;
  format?: 'pct' | 'bps' | 'days' | 'usd' | 'number';
  positiveIsBad?: boolean;
  sub?: string;
}

function formatValue(value: number, format: ImpactBarProps['format']): string {
  switch (format) {
    case 'pct':
      return `${value >= 0 ? '+' : ''}${value.toFixed(1)}%`;
    case 'bps':
      return `${value >= 0 ? '+' : ''}${value.toFixed(0)} bps`;
    case 'days':
      return `${value.toFixed(1)} d`;
    case 'usd':
      return `$${value.toFixed(2)}`;
    default:
      return value.toFixed(1);
  }
}

export function ImpactBar({
  label,
  value,
  max,
  format = 'number',
  positiveIsBad = true,
  sub,
}: ImpactBarProps) {
  const safeMax = max <= 0 ? Math.max(Math.abs(value), 1) : max;
  const pct = Math.max(0, Math.min(100, (Math.abs(value) / safeMax) * 100));
  const bad = positiveIsBad ? value > 0 : value < 0;
  const barColor = bad ? 'bg-red-500/70' : 'bg-emerald-500/70';
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900 p-3">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs uppercase tracking-wider text-slate-400">{label}</span>
        <span className={`text-sm font-semibold tabular-nums ${bad ? 'text-red-300' : 'text-emerald-300'}`}>
          {formatValue(value, format)}
        </span>
      </div>
      <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-slate-800">
        <div className={`h-full ${barColor}`} style={{ width: `${pct}%` }} />
      </div>
      {sub && <div className="mt-1.5 text-[11px] text-slate-500">{sub}</div>}
    </div>
  );
}

export default ImpactBar;
