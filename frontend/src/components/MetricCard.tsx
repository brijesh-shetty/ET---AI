import type { RiskTier } from "../lib/types";

interface Trend {
  direction: "up" | "down" | "flat";
  delta: number;
  format?: "pct" | "abs";
}

interface MetricCardProps {
  label: string;
  value: string | number;
  subValue?: string;
  tier?: RiskTier;
  trend?: Trend;
}

const TIER_BORDER: Record<RiskTier, string> = {
  low: "border-l-emerald-500",
  elevated: "border-l-amber-500",
  high: "border-l-orange-500",
  critical: "border-l-red-600",
};

const TREND_COLOR: Record<Trend["direction"], string> = {
  up: "text-emerald-400",
  down: "text-red-400",
  flat: "text-slate-400",
};

const TREND_ARROW: Record<Trend["direction"], string> = {
  up: "▲",
  down: "▼",
  flat: "─",
};

export function MetricCard({ label, value, subValue, tier, trend }: MetricCardProps) {
  const borderClass = tier ? TIER_BORDER[tier] : "border-l-slate-700";

  return (
    <div
      className={`rounded-lg border border-slate-800 ${borderClass} border-l-4 bg-slate-900 p-4`}
    >
      <div className="text-xs font-medium uppercase tracking-wider text-slate-500">
        {label}
      </div>
      <div className="mt-2 flex items-baseline gap-2">
        <span className="text-3xl font-semibold tabular-nums text-slate-100">
          {typeof value === "number" ? value.toFixed(2) : value}
        </span>
        {trend && (
          <span className={`text-xs ${TREND_COLOR[trend.direction]}`}>
            {TREND_ARROW[trend.direction]}{" "}
            {trend.format === "pct"
              ? `${(trend.delta * 100).toFixed(1)}%`
              : trend.delta.toFixed(2)}
          </span>
        )}
      </div>
      {subValue && (
        <div className="mt-1 text-xs text-slate-400">{subValue}</div>
      )}
    </div>
  );
}
