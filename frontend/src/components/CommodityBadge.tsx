import { COMMODITY_LABEL, type Commodity } from '@/lib/types';

interface CommodityBadgeProps {
  commodity: Commodity;
  size?: 'sm' | 'md';
}

const COMMODITY_COLOR: Record<Commodity, string> = {
  crude_oil: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
  lng: 'bg-sky-500/15 text-sky-300 border-sky-500/30',
  coking_coal: 'bg-stone-500/15 text-stone-300 border-stone-500/30',
  lithium: 'bg-fuchsia-500/15 text-fuchsia-300 border-fuchsia-500/30',
  cobalt: 'bg-blue-500/15 text-blue-300 border-blue-500/30',
  nickel: 'bg-teal-500/15 text-teal-300 border-teal-500/30',
  rare_earths: 'bg-violet-500/15 text-violet-300 border-violet-500/30',
  solar_pv: 'bg-yellow-500/15 text-yellow-300 border-yellow-500/30',
  uranium: 'bg-lime-500/15 text-lime-300 border-lime-500/30',
  lpg: 'bg-orange-500/15 text-orange-300 border-orange-500/30',
  atf: 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30',
};

export function CommodityBadge({ commodity, size = 'sm' }: CommodityBadgeProps) {
  const color = COMMODITY_COLOR[commodity] ?? 'bg-slate-700/30 text-slate-300 border-slate-600';
  const sizing = size === 'sm' ? 'text-[10px] px-1.5 py-0.5' : 'text-xs px-2 py-0.5';
  return (
    <span
      className={`inline-flex items-center rounded border uppercase tracking-wider ${sizing} ${color}`}
    >
      {COMMODITY_LABEL[commodity] ?? commodity}
    </span>
  );
}

export default CommodityBadge;
