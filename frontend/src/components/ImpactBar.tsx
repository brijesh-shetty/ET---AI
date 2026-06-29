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
  const barColor = bad ? 'bg-op-danger/70' : 'bg-op-good/70';
  const textColor = bad ? 'text-op-danger' : 'text-op-good';
  return (
    <div className="rounded-md border border-op-border bg-op-panel p-3">
      <div className="flex items-center justify-between gap-2">
        <span className="text-micro uppercase tracking-wider text-op-ink3">{label}</span>
        <span className={`font-mono text-sm font-medium tabular-nums ${textColor}`}>
          {formatValue(value, format)}
        </span>
      </div>
      <div className="mt-2 h-[3px] w-full overflow-hidden rounded-sm bg-op-panel3">
        <div className={`h-full ${barColor}`} style={{ width: `${pct}%` }} />
      </div>
      {sub && <div className="mt-1.5 text-meta text-op-ink3">{sub}</div>}
    </div>
  );
}

export default ImpactBar;
