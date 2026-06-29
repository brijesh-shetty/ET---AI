# Resilience Grid

**An operational intelligence layer for India's strategic import basket.** Fuses geopolitical events, vessel AIS, sanctions registries and commodity prices into composite corridor-level risk scores. Models named disruption scenarios. Solves a linear program for Strategic Petroleum Reserve drawdown. Drafts an analyst-grade narrative via Gemini.

Built for the ET AI Hackathon 2026 (Problem Statement 2).

---

## Why this matters

India imports roughly 88% of its crude oil, with 40-45% of those barrels transiting the Strait of Hormuz. Around 50% of natural gas arrives as LNG, primarily from Qatar, the US, the UAE and Australia. Coking coal — the feedstock for primary steel — is about 85% imported, with ~70% from Queensland through the Strait of Malacca. About 80% of solar PV modules and 60% of cells come from China, and over 90% of refined rare earths pass through Chinese processors. A single corridor incident or sanctions action ripples across power, mobility, steel and the clean-energy transition.

Strategic Petroleum Reserves cover only ~9.5 days of consumption. McKinsey's analysis of past energy supply shocks found that economies without integrated response intelligence took an average of 47 days longer to stabilise supply. **That intelligence layer is what this platform builds.**

## What it does, today

| Capability | Where it lives |
|---|---|
| Live composite risk scores per corridor × commodity (0-100, four tiers) | Dashboard / `/api/scores` |
| Geospatial digital twin — 5 corridors, vessel density, port status | `/twin` / `/api/digital-twin/state` |
| 7 named disruption scenarios with elasticity-based projections | `/scenarios/:name` / `POST /api/scenarios/{name}/run` |
| Side-by-side scenario comparison with deltas | `/compare` |
| 63-cell stress-test matrix (7 scenarios × 3 intensities × 3 durations) | `/stress-test` |
| Historical backtest with day-by-day playback (June 2025 Hormuz, Dec 2024 Red Sea, Q4 2024 Queensland coal) | `/backtest` |
| SPR drawdown linear program (PuLP CBC) | `/spr` / `POST /api/spr/plan` |
| Alternative-supplier ranking by risk + share + lead-time | `/sourcing` / `/api/sourcing/{commodity}` |
| Cost-of-inaction calculator (Rs crore/day, GDP-bps-driven) | `/api/cost-of-inaction` |
| OFAC sanctions alerts cross-referenced with vessels | Banner on dashboard |
| WebSocket live feed — new alert pushed every 8 seconds | `/ws/feed` |
| Ask-the-analyst chat panel (Gemini-backed) | floating bottom-right on every page |
| Slack alert webhook | `POST /api/integrations/slack` |

## Repository layout

```
backend/        FastAPI service
  app/api/      routes.py (17 endpoints, all camelCase JSON), websocket.py
  app/engines/  risk_score, scenarios (7), spr_lp (PuLP CBC), sourcing
  app/ingest/   9 source adapters: gdelt, ais, sanctions, prices, lng, coal, minerals, solar, news
  app/llm/      Gemini client (summarise, prompts) with offline fixture fallback
  data/fixtures/ 10 JSON snapshots — demo runs without any API key
frontend/       React 18 + Vite + TypeScript + Tailwind
  src/pages/    9 pages: Dashboard, DigitalTwin, Scenarios, ScenarioRun,
                ScenarioCompare, StressTest, Backtest, Sourcing, SPR
  src/components/  including ChatDrawer, SanctionAlertBanner, CostStrip,
                   CommodityTicker, MetricCard, RiskTicker, ImpactBar
  src/lib/      api.ts (typed client), types.ts (shape contract), ws.ts, store.ts, fmt.ts
docs/           architecture.md, assumptions.md, demo_script.md, presentation_outline.md
```

## Quickstart

**Prerequisites:** Python 3.11+, Node 20+, ~1 GB free disk.

Backend (Windows PowerShell):

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]
Copy-Item ..\.env.example .\.env       # then edit .env if you want live LLM calls
uvicorn app.main:app --reload --port 8000
```

Frontend (in a second terminal):

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. OpenAPI docs at `http://localhost:8000/docs`.

**The demo runs offline.** With `ALLOW_LIVE_INGEST=false` (default) it uses pinned JSON fixtures and pre-canned Gemini outputs — every page works without any API key.

## Live mode (Gemini)

To enable real LLM calls, set in `backend/.env`:

```
GEMINI_API_KEY=<your key from https://aistudio.google.com/apikey>
ALLOW_LIVE_INGEST=true
```

The narrative layer uses `gemini-2.5-flash` for synthesis and the lite variant for high-frequency classification. The whole hackathon scope costs well under USD 1 of Gemini quota.

To enable Slack alerts, additionally set:

```
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
```

Without the webhook, the "Send to Slack" button returns a dry-run payload so the UI degrades gracefully.

## Where the intelligence lives

- `backend/app/engines/risk_score.py` — composite 0-100 corridor score: 40% geopolitical + 25% chokepoint + 15% sanctions + 20% market volatility
- `backend/app/engines/scenarios.py` — `SCENARIOS` dict + per-scenario elasticity parameters; routes.py reads these directly via `_project_impact(name, intensity, duration)`
- `backend/app/engines/spr_lp.py` — PuLP CBC LP: minimise integrated price-impact subject to reserve, injection-rate and consumption constraints
- `backend/app/engines/sourcing.py` — ranks alternatives by `0.5 × (1 - current_risk) + 0.3 × historical_share + 0.2 × lead_time_score`
- `backend/app/llm/summarise.py` — Gemini wrapper, async, LRU-cached, fixture fallback

## Demo flow (5 minutes)

1. **Dashboard** — point to live corridor risk scores. The sanctions banner shows an OFAC-flagged tanker. The narrated feed updates live via WebSocket.
2. **Digital twin** — pan over Arabian Sea. Click the Hormuz dot to trigger the closure scenario.
3. **Scenario run** — Brent $82 → $91.5, SPR runway 9.5 → 5.1 days, GDP -45 bps. Cost-of-inaction shows ₹ crore/day. Analyst narrative below cites the input signals.
4. **Compare** — side-by-side Hormuz partial closure vs Red Sea suspension. Deltas highlight differential risk.
5. **Stress test** — the full 63-cell matrix. Worst case highlighted. Then **SPR optimiser** — solve the LP, see drawdown vs flat baseline.

Full narrated script: [docs/demo_script.md](docs/demo_script.md).

## Tech stack

Python 3.11, FastAPI, Pydantic v2, PuLP, google-generativeai, structlog, aiohttp, websockets
React 18, Vite, TypeScript, Tailwind, react-router-dom, axios, zustand, Recharts, Leaflet, react-leaflet, lucide-react, clsx, date-fns

## Honest scope

The procurement / sourcing module ranks alternatives. It does **not** validate refinery configuration, coal washability, lithium chemistry or rare-earth separation. Those require a domain partner; we say so on screen. AIS spoofing near Iran is real — we acknowledge that vessel attribution is not 100% reliable in disputed waters.

See [docs/assumptions.md](docs/assumptions.md) for every numeric baseline and modelling assumption.

## License

MIT for the source. Third-party data — GDELT, OFAC SDN, EIA, AISStream, OpenStreetMap, Sentinel, PPAC, GIIGNL, USGS, MNRE, World Bank, NewsAPI — remains under the licenses of their respective providers. Used here for non-commercial research and demonstration.
