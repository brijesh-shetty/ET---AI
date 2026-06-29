import { useState } from 'react';
import type { FeedItem } from '../lib/types';
import { tierFromImportance } from '../lib/fmt';
import { RiskBadge } from './RiskBadge';

interface RiskTickerProps {
  items: FeedItem[];
}

function formatTime(ts: string | undefined): string {
  if (!ts) return '--';
  try {
    const d = new Date(ts);
    if (Number.isNaN(d.getTime())) return ts;
    return d.toLocaleTimeString('en-IN', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    });
  } catch {
    return ts;
  }
}

export function RiskTicker({ items }: RiskTickerProps) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const toggle = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  if (!items || items.length === 0) {
    return (
      <div className="rounded-lg border border-slate-800 bg-slate-900 p-6 text-sm text-slate-500">
        No active risk alerts.
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900">
      <div className="flex items-center justify-between border-b border-slate-800 px-4 py-3">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-300">
          Risk feed
        </h3>
        <span className="flex items-center gap-2 text-xs text-slate-500">
          <span className="h-2 w-2 animate-pulse rounded-full bg-indigo-500" />
          live
        </span>
      </div>
      <div className="max-h-[28rem] overflow-y-auto divide-y divide-slate-800">
        {items.map((item) => {
          const id = item.id ?? `${item.source}-${item.publishedAt}`;
          const tier = tierFromImportance(item.importance);
          const isOpen = expanded.has(id);
          return (
            <div key={id} className="px-4 py-3 hover:bg-slate-800/40">
              <button
                type="button"
                onClick={() => toggle(id)}
                className="flex w-full items-start gap-3 text-left"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                    <span>{formatTime(item.publishedAt)}</span>
                    <RiskBadge tier={tier} score={item.importance * 10} showScore={false} />
                    {item.source && <span className="text-slate-600">- {item.source}</span>}
                    {item.commodity && <span className="text-slate-600">- {item.commodity}</span>}
                  </div>
                  <p className="mt-1 text-sm text-slate-100 line-clamp-2">{item.headline}</p>
                </div>
              </button>
              {isOpen && (
                <div className="ml-1 mt-2 border-l border-slate-800 pl-3">
                  <p className="text-sm leading-relaxed text-slate-300">{item.summary}</p>
                  {item.url && (
                    <div className="mt-2">
                      <a
                        href={item.url}
                        target="_blank"
                        rel="noreferrer"
                        className="rounded border border-slate-700 px-2 py-0.5 text-xs text-indigo-400 hover:border-indigo-500"
                      >
                        {item.source ?? 'Source'}
                      </a>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default RiskTicker;
