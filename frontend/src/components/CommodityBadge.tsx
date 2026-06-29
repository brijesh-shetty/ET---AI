import { COMMODITY_LABEL, type Commodity } from '@/lib/types';

interface CommodityBadgeProps {
  commodity: Commodity;
  size?: 'sm' | 'md';
}

const COMMODITY_TONE: Record<Commodity, string> = {
  crude_oil: 'border-op-warn/50 text-op-warn',
  lng: 'border-op-accent/50 text-op-accent',
  coking_coal: 'border-op-ink3 text-op-ink2',
  lithium: 'border-fuchsia-400/40 text-fuchsia-300',
  cobalt: 'border-sky-400/40 text-sky-300',
  nickel: 'border-teal-400/40 text-teal-300',
  rare_earths: 'border-violet-400/40 text-violet-300',
  solar_pv: 'border-yellow-400/40 text-yellow-300',
  uranium: 'border-lime-400/40 text-lime-300',
  lpg: 'border-orange-400/40 text-orange-300',
  atf: 'border-cyan-400/40 text-cyan-300',
};

export function CommodityBadge({ commodity, size = 'sm' }: CommodityBadgeProps) {
  const tone = COMMODITY_TONE[commodity] ?? 'border-op-border text-op-ink2';
  const sizing = size === 'sm' ? 'text-micro px-1.5 py-0.5' : 'text-meta px-2 py-0.5';
  return (
    <span
      className={`inline-flex items-center rounded-sm border font-mono uppercase tracking-wider ${sizing} ${tone}`}
    >
      {COMMODITY_LABEL[commodity] ?? commodity}
    </span>
  );
}

export default CommodityBadge;
