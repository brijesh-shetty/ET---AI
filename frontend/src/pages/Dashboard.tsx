import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  getExecutiveBrief,
  getFeed,
  getScenarios,
  getScores,
} from "@/lib/api";
import { fmtNumber, fmtPct, fmtTime, tierAccent } from "@/lib/fmt";
import { RiskTicker } from "@/components/RiskTicker";
import {
  COMMODITY_LABEL,
  CORRIDOR_LABEL,
  type Corridor,
  type ExecutiveBrief,
  type FeedItem,
  type RiskScore,
  type RiskTier,
} from "@/lib/types";

interface ScenarioMeta {
  name: string;
  label: string;
  description: string;
  primary_commodity: string;
  primary_corridor: Corridor;
}

const HERO_CORRIDORS: Corridor[] = [
  "hormuz",
  "bab_el_mandeb",
  "malacca",
  "south_china_sea",
];

const HERO_TITLE: Record<Corridor, string> = {
  hormuz: "Hormuz",
  bab_el_mandeb: "Bab el-Mandeb",
  malacca: "Malacca",
  south_china_sea: "China route",
  cape_of_good_hope: "Cape",
  suez: "Suez",
};

const REFRESH_MS = 60_000;

function aggregateCorridor(scores: RiskScore[], corridor: Corridor): {
  score: number;
  tier: RiskTier;
  drivers: string[];
} | null {
  const subset = scores.filter((s) => s.corridor === corridor);
  if (subset.length === 0) return null;
  const top = subset.reduce((a, b) => (a.score >= b.score ? a : b));
  const drivers = Array.from(new Set(subset.flatMap((s) => s.drivers ?? []))).slice(0, 3);
  return { score: top.score, tier: top.tier, drivers };
}

function MetricCard({
  title,
  score,
  tier,
  drivers,
}: {
  title: string;
  score: number | null;
  tier: RiskTier | null;
  drivers: string[];
}) {
  const accent = tier ? tierAccent(tier) : { border: "border-slate-800", text: "text-slate-400", dot: "bg-slate-600" };
  return (
    <div className={`rounded-lg border ${accent.border} bg-slate-900 p-5`}>
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
          {title}
        </h3>
        <span className={`h-2.5 w-2.5 rounded-full ${accent.dot}`} />
      </div>
      <div className="mt-3 flex items-baseline gap-2">
        <span className={`text-3xl font-semibold tabular-nums ${accent.text}`}>
          {score === null ? "--" : score.toFixed(0)}
        </span>
        <span className="text-xs uppercase tracking-wide text-slate-500">
          {tier ?? "no signal"}
        </span>
      </div>
      <ul className="mt-3 space-y-1 text-xs text-slate-400">
        {drivers.length === 0 ? (
          <li className="text-slate-600">No active drivers</li>
        ) : (
          drivers.map((d, i) => (
            <li key={i} className="line-clamp-1">
              - {d}
            </li>
          ))
        )}
      </ul>
    </div>
  );
}

function ScenarioCard({ meta }: { meta: ScenarioMeta }) {
  return (
    <Link
      to={`/scenarios/${meta.name}`}
      className="block rounded-lg border border-slate-800 bg-slate-900 p-4 transition hover:border-indigo-500/60 hover:bg-slate-800/60"
    >
      <div className="flex items-start justify-between gap-2">
        <h4 className="text-sm font-semibold text-slate-100">{meta.label}</h4>
        <span className="rounded border border-slate-700 px-1.5 py-0.5 text-[10px] uppercase tracking-wider text-slate-400">
          {CORRIDOR_LABEL[meta.primary_corridor] ?? meta.primary_corridor}
        </span>
      </div>
      <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-slate-400">
        {meta.description}
      </p>
      <div className="mt-3 text-[11px] uppercase tracking-wider text-indigo-400">
        Run scenario &rarr;
      </div>
    </Link>
  );
}

function ExecutiveBriefPanel({ brief }: { brief: ExecutiveBrief | null }) {
  if (!brief) {
    return (
      <div className="rounded-lg border border-slate-800 bg-slate-900 p-6 text-sm text-slate-500">
        Executive brief loading...
      </div>
    );
  }
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900">
      <div className="flex items-center justify-between border-b border-slate-800 px-5 py-3">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-300">
          Daily executive brief
        </h3>
        <span className="text-xs text-slate-500">{fmtTime(brief.generatedAt)}</span>
      </div>
      <div className="grid gap-6 px-5 py-5 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <h4 className="text-lg font-semibold text-slate-100">{brief.headline}</h4>
          <p className="mt-2 text-sm leading-relaxed text-slate-300">{brief.summary}</p>
          {brief.actions && brief.actions.length > 0 && (
            <div className="mt-4">
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                Recommended actions
              </p>
              <ul className="mt-2 space-y-1.5 text-sm text-slate-300">
                {brief.actions.slice(0, 5).map((a, i) => (
                  <li key={i} className="flex gap-2">
                    <span className="text-indigo-400">&bull;</span>
                    <span>{a}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
            Market snapshot
          </p>
          <dl className="mt-2 space-y-1.5 text-sm">
            <div className="flex justify-between border-b border-slate-800 pb-1">
              <dt className="text-slate-400">Brent</dt>
              <dd className="tabular-nums text-slate-200">
                ${fmtNumber(brief.marketSnapshot?.brentUsd, 2)}
              </dd>
            </div>
            <div className="flex justify-between border-b border-slate-800 pb-1">
              <dt className="text-slate-400">TTF</dt>
              <dd className="tabular-nums text-slate-200">
                {fmtNumber(brief.marketSnapshot?.ttfEurMwh, 2)} EUR/MWh
              </dd>
            </div>
            <div className="flex justify-between border-b border-slate-800 pb-1">
              <dt className="text-slate-400">INR/USD</dt>
              <dd className="tabular-nums text-slate-200">
                {fmtNumber(brief.marketSnapshot?.inrUsd, 2)}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-400">Coal AUD</dt>
              <dd className="tabular-nums text-slate-200">
                {fmtNumber(brief.marketSnapshot?.coalAud, 2)}
              </dd>
            </div>
          </dl>
          {brief.topRisks && brief.topRisks.length > 0 && (
            <div className="mt-4">
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                Top risks
              </p>
              <ul className="mt-2 space-y-1.5 text-xs text-slate-300">
                {brief.topRisks.slice(0, 4).map((r, i) => (
                  <li key={i}>
                    <span className="text-slate-100">
                      {CORRIDOR_LABEL[r.corridor]} / {COMMODITY_LABEL[r.commodity]}
                    </span>
                    <span className="ml-1 text-slate-500">- {r.note}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
      {brief.citations && brief.citations.length > 0 && (
        <div className="flex flex-wrap gap-2 border-t border-slate-800 px-5 py-3">
          {brief.citations.map((c, i) => (
            <a
              key={i}
              href={c.url}
              target="_blank"
              rel="noreferrer"
              className="rounded border border-slate-700 px-2 py-0.5 text-[11px] text-indigo-400 hover:border-indigo-500"
            >
              {c.label}
            </a>
          ))}
        </div>
      )}
    </div>
  );
}

export default function Dashboard() {
  const [scores, setScores] = useState<RiskScore[]>([]);
  const [feed, setFeed] = useState<FeedItem[]>([]);
  const [scenarios, setScenarios] = useState<ScenarioMeta[]>([]);
  const [brief, setBrief] = useState<ExecutiveBrief | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loadedAt, setLoadedAt] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [s, f, c, b] = await Promise.all([
          getScores(),
          getFeed(),
          getScenarios(),
          getExecutiveBrief(),
        ]);
        if (cancelled) return;
        setScores(s);
        setFeed(f);
        setScenarios(c);
        setBrief(b);
        setLoadedAt(new Date().toISOString());
        setError(null);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Failed to load dashboard");
      }
    }

    load();
    const interval = setInterval(load, REFRESH_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  const heroCards = useMemo(() => {
    return HERO_CORRIDORS.map((corridor) => {
      const agg = aggregateCorridor(scores, corridor);
      return {
        title: `${HERO_TITLE[corridor]} risk`,
        score: agg?.score ?? null,
        tier: agg?.tier ?? null,
        drivers: agg?.drivers ?? [],
      };
    });
  }, [scores]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto max-w-7xl px-6 py-8">
        <header className="mb-8 flex items-end justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-indigo-400">
              ET AI Hackathon 2026 / PS2
            </p>
            <h1 className="mt-1 text-2xl font-semibold tracking-tight">
              Energy supply chain resilience
            </h1>
            <p className="mt-1 text-sm text-slate-400">
              Composite risk across maritime corridors, refreshed every {fmtPct(REFRESH_MS / 60_000, 0, "min")}.
            </p>
          </div>
          <div className="text-right text-xs text-slate-500">
            {loadedAt ? `Last refresh ${fmtTime(loadedAt)}` : "Loading..."}
            {error && <div className="mt-1 text-red-400">{error}</div>}
          </div>
        </header>

        <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {heroCards.map((c) => (
            <MetricCard
              key={c.title}
              title={c.title}
              score={c.score}
              tier={c.tier}
              drivers={c.drivers}
            />
          ))}
        </section>

        <section className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-2">
          <div>
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">
              Narrated feed
            </h2>
            <RiskTicker items={feed} />
          </div>
          <div>
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">
              Stress scenarios
            </h2>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {scenarios.length === 0 ? (
                <div className="col-span-2 rounded-lg border border-slate-800 bg-slate-900 p-6 text-sm text-slate-500">
                  Loading scenarios...
                </div>
              ) : (
                scenarios.slice(0, 8).map((s) => <ScenarioCard key={s.name} meta={s} />)
              )}
            </div>
          </div>
        </section>

        <section className="mt-8">
          <ExecutiveBriefPanel brief={brief} />
        </section>
      </div>
    </div>
  );
}
