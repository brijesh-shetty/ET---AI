import { create } from 'zustand';
import type { Commodity, Corridor, RiskScore, FeedItem } from './types';

interface AppState {
  selectedCorridor: Corridor | null;
  selectedCommodity: Commodity | null;
  liveScores: RiskScore[];
  liveFeed: FeedItem[];
  lastFetched: string | null;
  live: boolean;

  setSelectedCorridor: (c: Corridor | null) => void;
  setSelectedCommodity: (c: Commodity | null) => void;
  setLiveScores: (s: RiskScore[]) => void;
  setLiveFeed: (f: FeedItem[]) => void;
  markFetched: () => void;
  setLive: (live: boolean) => void;
  reset: () => void;
}

export const useAppStore = create<AppState>((set) => ({
  selectedCorridor: null,
  selectedCommodity: null,
  liveScores: [],
  liveFeed: [],
  lastFetched: null,
  live: true,

  setSelectedCorridor: (c) => set({ selectedCorridor: c }),
  setSelectedCommodity: (c) => set({ selectedCommodity: c }),
  setLiveScores: (s) => set({ liveScores: s, lastFetched: new Date().toISOString() }),
  setLiveFeed: (f) => set({ liveFeed: f }),
  markFetched: () => set({ lastFetched: new Date().toISOString() }),
  setLive: (live) => set({ live }),
  reset: () =>
    set({
      selectedCorridor: null,
      selectedCommodity: null,
      liveScores: [],
      liveFeed: [],
      lastFetched: null,
    }),
}));

export function topScoreFor(scores: RiskScore[], corridor: Corridor): RiskScore | null {
  const subset = scores.filter((s) => s.corridor === corridor);
  if (subset.length === 0) return null;
  return subset.reduce((a, b) => (a.score >= b.score ? a : b));
}

export function commoditiesInScores(scores: RiskScore[]): Commodity[] {
  return Array.from(new Set(scores.map((s) => s.commodity)));
}
