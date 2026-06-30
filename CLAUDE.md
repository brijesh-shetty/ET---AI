# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

PS2 of the ET AI Hackathon 2026 — "AI-Driven Energy Supply Chain Resilience for Import-Dependent Economies". A signal-to-decision platform fusing geopolitical events (GDELT), vessel AIS, OFAC sanctions, and commodity prices into composite risk scores for India's strategic imports: crude oil, LNG, coking coal, lithium, cobalt, nickel, rare earths, solar PV, uranium. Includes a digital-twin map, 7 named disruption scenarios with elasticity-based projections, a PuLP-based Strategic Petroleum Reserve LP solver, and a Gemini-powered narrative layer.

Multi-commodity, multi-corridor coverage is the deliberate differentiator. Most PS2 entries will scope to crude oil only.

## Common commands

Backend (Python 3.11 + FastAPI):
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]
copy ..\.env.example .env       # then edit .env (see "Environment" below)
uvicorn app.main:app --reload --port 8000
```

Frontend (Vite + React 18 + TS):
```powershell
cd frontend
npm install
npm run dev                      # http://localhost:5173, proxies /api and /ws to :8000
npx tsc --noEmit                 # type-check only, no emit — fastest sanity check
npm run build                    # production build
```

Endpoint smoke test (catches contract breaks early):
```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -c "from fastapi.testclient import TestClient; from app.main import app; c = TestClient(app); print(c.get('/api/healthz').json())"
```

Re-install after editing `pyproject.toml`: `pip install -e .` again. New deps don't auto-install on uvicorn reload.

Vite proxy is only re-read on **full restart** (Ctrl+C → `npm run dev`), not HMR. If WebSocket frames aren't arriving on the dashboard, the proxy didn't reload.

## Architecture in three layers

**Signal ingestion** — `backend/app/ingest/*.py`. One module per source (gdelt, ais, sanctions, commodity_prices, lng, coal, minerals, solar, news). Each async function checks `settings.allow_live_ingest`; when false (default) it returns fixtures from `backend/data/fixtures/*.json`. This is the demo's safety net — the whole product runs end-to-end without any API key.

**Engines** — `backend/app/engines/`. Function-based, not class-based:
- `risk_score.compute_corridor_score(corridor, signals) -> RiskScore` — composite 0-100 from 40% geopolitical + 25% chokepoint + 15% sanctions + 20% market volatility.
- `scenarios.SCENARIOS` dict + 7 per-scenario elasticity helpers (`_hormuz_partial_closure`, `_australia_coking_coal`, etc.). **`scenarios.run_scenario()` is broken** — it builds a `ScenarioResult` Pydantic model with wrong field names. `routes.py` bypasses it via its own `_project_impact(name, intensity, duration)` helper that reads `SCENARIOS[name].params` directly. Do not call `run_scenario()` from new code.
- `spr_lp.solve_spr_plan(SPRConfig) -> SPRPlan` — PuLP CBC linear program over daily drawdown/replenish. `SPRPlan` shape: `{days, drawdown_kbpd, replenish_kbpd, reserve_mmb, status, ...}`.
- `sourcing.rank_alternatives(commodity, disrupted_source)` — composite-score ranking, returns dataclasses (not Pydantic). Has its own `Commodity` enum separate from `app.models.Commodity`.

**HTTP surface** — `backend/app/api/routes.py` mounted at `/api`. Returns JSON dicts in **camelCase to match the frontend TS contract**, not the Pydantic snake_case models. `routes.py` is the integration layer; it does not use `app.models` for output shapes. WebSocket `/ws/feed` is in `backend/app/api/websocket.py`, registered separately via `app.add_api_websocket_route("/ws/feed", ws_feed)` (no `/api` prefix).

LLM layer is `backend/app/llm/{summarise.py, prompts.py}`. Uses `google-generativeai` SDK (Gemini). Fixture fallback kicks in when `GEMINI_API_KEY` is unset OR `ALLOW_LIVE_INGEST=false`. Cache is in-memory LRU keyed on prompt hash. Class is `LLMClient`; methods: `summarise_risk`, `narrate_scenario`, `draft_recommendation`, `executive_brief`, `chat`.

## Endpoint inventory (23 REST routes + WS)

```
GET  /api/healthz                          GET  /api/scenarios
GET  /api/scores                           POST /api/scenarios/{name}/run
GET  /api/scores/{corridor}                GET  /api/digital-twin/state  [has sanctionAlerts]
GET  /api/scores/suppliers/{commodity}     GET  /api/feed
GET  /api/sourcing/{commodity}             GET  /api/executive-brief
POST /api/sourcing/{commodity}/analyse     GET  /api/commodities
GET  /api/sourcing/{commodity}/substitutes GET  /api/backtest/events
GET  /api/impact-cascade/causes            GET  /api/backtest/{id}/replay
POST /api/impact-cascade                   GET  /api/stress-test
GET  /api/spr/plan                         POST /api/chat
POST /api/spr/plan                         POST /api/integrations/slack
GET  /api/cost-of-inaction
WS   /ws/feed
```

Route ordering matters: `GET /api/scores/suppliers/{commodity}` is declared **before** `GET /api/scores/{corridor}` in `routes.py` so the literal `suppliers` segment isn't swallowed by the `{corridor}` path param. When adding a literal-segment route that shares a prefix with an existing `{param}` route at the same depth, declare it first.

`/stress-test` and `/backtest/{id}/replay` return wrapped objects (`{cells: [...]}` and `{timeline: [...]}` respectively). The frontend `getStressTest()` and `getBacktestReplay()` unwrap them — keep that convention if you add similar endpoints.

## Frontend conventions

`frontend/src/lib/types.ts` is the single source of truth for shapes. Pages and components reference its interfaces and label dictionaries (`CORRIDOR_LABEL`, `COMMODITY_LABEL`, `TIER_COLOR`). When you add a backend field, add it to `types.ts` and the matching function in `lib/api.ts` in the same commit.

Design tokens live on the `op` Tailwind namespace (`op-bg`, `op-panel`, `op-panel2`, `op-border`, `op-ink`, `op-accent #00d4aa`, etc.). Fonts: Inter (UI), IBM Plex Mono (numbers, `font-mono`), Newsreader (editorial italic, `font-serif`). All data numbers must be `tabular-nums`. No `animate-pulse`/`animate-ping` — liveness is shown via timestamps, not animated dots.

ChatDrawer is mounted globally in `App.tsx` and toggled via the zustand `useAppStore.toggleChat()`. WebSocket connection is established in `Dashboard.tsx::useEffect` via `connectFeedWebSocket()` from `lib/ws.ts`.

## Environment

`.env.example` is the canonical list. Required for live mode:
- `GEMINI_API_KEY` — Google AI Studio key (https://aistudio.google.com/apikey)
- `GEMINI_MODEL=gemini-2.5-flash` (default), `GEMINI_MODEL_FAST=gemini-2.5-flash-lite-preview-06-17`
- `ALLOW_LIVE_INGEST=true` to enable real API calls. Default `false` runs the demo from fixtures.

Optional:
- `AISSTREAM_API_KEY`, `EIA_API_KEY`, `ALPHA_VANTAGE_KEY`, `NEWSAPI_KEY`
- `SLACK_WEBHOOK_URL` — if unset, `/api/integrations/slack` returns `{sent: false, reason: ..., dryRun: ...}` so the UI can show a graceful fallback.

Note: `google-generativeai` SDK emits a deprecation warning in favor of `google-genai`. The old SDK still functions; swap is non-urgent.

## Honest scoping (do not overclaim)

`docs/assumptions.md` is the single source of truth for what we model and what we do NOT. The procurement / sourcing module ranks alternatives by composite risk + historical share + lead time. It deliberately does **NOT** model:
- Refinery configuration or crude grade chemistry (API gravity, sulfur, NMR)
- Coking coal grade differentiation (hard/semi-soft/PCI, washability, CSR)
- Lithium chemistry (carbonate vs hydroxide), NMC vs LFP implications
- Rare earth separation (China controls ~90% of refining — acknowledged on screen)
- Solar module efficiency / TOPCon vs HJT premium
- Tanker rate spot data (Baltic Exchange BDTI is paid; use headline numbers only)

Industry judges will probe these. The fix is honest scoping, not pretending to know more.

## Fixtures vs live

`backend/data/fixtures/*.json` (11 files): gdelt_events, vessels, sanctions, commodity_prices, india_imports, refineries, lng_terminals, critical_minerals, solar_imports, llm_responses, dependency_graph. These are the demo's safety net. When adding a new endpoint that depends on a source, write a fixture in the same PR. (Backtest events are not a fixture file — they're defined inline in `engines/cascade.py` / `routes.py`. `dependency_graph.json` feeds the impact-cascade engine.)

AIS spoofing near Iran is real. Do not claim 100% vessel attribution. PPAC, DGMS, MNRE data has a 30-45 day lag — flag scenario projections as such, not "today's" import figures.

## What's done (committed)

### Signal ingestion (all 9 modules)
- **GDELT** — geopolitical event density + tone near each corridor.
- **AIS** — vessel position anomaly detection from AISStream.
- **OFAC sanctions** — sanctioned-entity matching on corridor traffic.
- **Commodity prices** — EIA (crude/gas) + Alpha Vantage (metals) + fixture fallback. Alpha Vantage key accepts both `ALPHA_VANTAGE_API_KEY` and `ALPHA_VANTAGE_KEY`.
- **LNG, coal, minerals, solar, news** — fixture-backed modules with live stubs.

### Engines (6 engines)
- **Risk score** (`risk_score.py`) — composite corridor scoring: 40% geo + 25% AIS + 15% sanctions + 20% price vol.
- **Live scores** (`live_scores.py`) — runs the scoring math over real per-signal data (live or fixture), per-commodity and per-supplier scoring via corridor relevance + import-share concentration.
- **Scenarios** (`scenarios.py`) — 7 named disruption scenarios with elasticity-based projections. Note: `run_scenario()` is broken; `routes.py` bypasses it via `_project_impact()`.
- **SPR LP** (`spr_lp.py`) — PuLP CBC linear program for SPR drawdown/replenish planning with scenario-driven gap inputs.
- **Sourcing** (`sourcing.py`) — composite-score alternative-supplier ranking by risk + historical share + lead time.
- **Impact cascade** (`cascade.py`) — dependency-graph BFS from any cause (corridor/country/commodity) to every downstream Indian sector and macro variable, with hop-decay severity.

### Frontend pages (10 pages)
- **Dashboard** — corridor risk heatmap, commodity ticker, live WebSocket feed, Gemini chat drawer.
- **Digital Twin** — Leaflet map with refineries, LNG terminals, ports, foreign supply sources, maritime routes, Indian energy distribution network (demand centres + product pipelines), corridor overlays, what-if scenario toggle.
- **Scenarios** — scenario catalogue cards with parameter summaries.
- **ScenarioRun** — run a scenario with intensity/duration sliders → timeline chart (Brent, SPR drawdown, Cape share) + sector trajectory chart (refinery run rate, diesel price, power stress, GDP growth).
- **ScenarioCompare** — side-by-side multi-scenario comparison.
- **SPR** — SPR optimiser with LP-driven drawdown/replenish schedule, cover-days gauge, gap-closed metrics.
- **Sourcing** — commodity-level alternative supplier ranking with risk breakdown.
- **Impact Cascade** — pick any cause → see the full downstream cascade through Indian sectors and macro indicators.
- **Stress Test** — multi-corridor simultaneous shock matrix.
- **Backtest** — replay historical events against the scoring engine.

### API surface (17 routes + WS)
All 17 REST endpoints and the `/ws/feed` WebSocket are implemented and served. See endpoint inventory above.

### Other
- Gemini LLM layer (`summarise_risk`, `narrate_scenario`, `draft_recommendation`, `executive_brief`, `chat`) with fixture fallback.
- Slack integration endpoint (dry-run when webhook is unset).
- Comprehensive assumption ledger in `docs/assumptions.md`.
- 11 fixture files for fully offline demo.

## What's in progress (uncommitted)

These changes are staged but not yet committed:

1. **Sector trajectory charts in ScenarioRun** — refinery run rate %, domestic diesel price (Rs/L), power-sector stress index, GDP growth trajectory under each scenario shock. Backend emits the new timeline fields; frontend renders a second `LineChart` with dual Y-axes.
2. **Indian energy distribution network on Digital Twin** — 8 domestic demand centres (Delhi NCR, Mumbai-Pune, Bengaluru, etc.) with demand index, fed-by refinery links, and dashed distribution pipeline polylines on the map. New `distribution` layer toggle.
3. **Alpha Vantage price fallback** — `commodity_prices.py` now tries EIA → Alpha Vantage → fixture in sequence. Config accepts both env var spellings.

## What we can still do (potential improvements)

### High impact for judges
- **Live demo toggle** — a UI switch to flip `ALLOW_LIVE_INGEST` and show judges that scores genuinely change with real GDELT/AIS data vs fixtures.
- **Executive brief page** — the `/api/executive-brief` endpoint exists but has no dedicated frontend page. A single-page printable PDF/HTML brief would be a strong closer in the demo.
- **Cost-of-inaction dashboard** — the `/api/cost-of-inaction` endpoint is wired; a dedicated card/page with cumulative GDP loss, import-bill delta, and SPR depletion timeline would sharpen the "why act now" argument.

### Medium effort, strong differentiator
- **Multi-scenario overlay** — overlay 2-3 scenario timelines on one chart to show compounding risk (e.g., Hormuz closure + Australia coal ban simultaneously).
- **Backtest replay visualisation** — the `/api/backtest/{id}/replay` endpoint returns timeline data; a chart/animation replaying a historical disruption would show the model validates against reality.
- **Sanction alert drill-down** — the digital twin already has `sanctionAlerts` in its state; a dedicated panel listing flagged entities with OFAC SDN match details would demonstrate AML/compliance capability.
- **WebSocket live-score push** — currently the WS feed sends canned events; wiring it to push live score updates when ingest data changes would show real-time responsiveness.

### Lower effort, polish
- **Dark/light theme toggle** — design tokens are already on the `op-*` namespace; wiring a toggle is mostly CSS variable swaps.
- **Mobile-responsive layout** — pages currently assume desktop; adding responsive breakpoints improves the demo on a projector.
- **Loading skeletons** — replace empty states with Tailwind skeleton loaders for a polished feel during API calls.
- **Export to CSV/PDF** — add download buttons on Sourcing, Stress Test, and Scenario pages for data export.
- **Unit tests for engines** — `risk_score`, `cascade`, and `spr_lp` are pure functions; property-based tests would strengthen confidence.
- **Fix `scenarios.run_scenario()`** — currently broken with wrong field names; the route bypasses it, but fixing the engine would clean up the architecture.

### Not in scope (honest limits)
See "Honest scoping" above and `docs/assumptions.md`. We do not model refinery chemistry, coal grades, lithium cell chemistry, rare earth separation, solar cell technology, or spot tanker rates.

## Reference docs

- `docs/architecture.md` — full system diagram, data-flow trace, scaling considerations
- `docs/architecture_diagram.md` — Mermaid + ASCII versions for the deck
- `docs/assumptions.md` — assumption ledger (numeric baselines, scenario parameters, what we don't model)
- `docs/demo_script.md` — 5-minute walkthrough with timing
- `docs/presentation_outline.md` — 10-slide deck outline
- `6a38ce305640d_ET_AI_Hackathon_2026_Problem_Statements.pdf` — PS2 is page 4-5
