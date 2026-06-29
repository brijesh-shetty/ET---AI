import { tierAccent } from '@/lib/fmt';
import type { RiskTier } from '@/lib/types';

interface RiskBadgeProps {
  tier: RiskTier;
  score?: number;
  showScore?: boolean;
  size?: 'sm' | 'md';
}

export function RiskBadge({ tier, score, showScore = true, size = 'sm' }: RiskBadgeProps) {
  const accent = tierAccent(tier);
  const sizing = size === 'sm' ? 'text-[10px] px-1.5 py-0.5' : 'text-xs px-2 py-1';
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded border uppercase tracking-wider ${sizing} ${accent.border} ${accent.bg} ${accent.text}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${accent.dot}`} />
      <span>{tier}</span>
      {showScore && typeof score === 'number' && (
        <span className="tabular-nums opacity-80">{score.toFixed(0)}</span>
      )}
    </span>
  );
}

export default RiskBadge;
