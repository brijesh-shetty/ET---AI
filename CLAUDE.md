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

## Endpoint inventory (17 routes)

```
GET  /api/healthz                          GET  /api/scenarios
GET  /api/scores                           POST /api/scenarios/{name}/run
GET  /api/scores/{corridor}                GET  /api/digital-twin/state  [has sanctionAlerts]
GET  /api/sourcing/{commodity}             GET  /api/feed
GET  /api/spr/plan                         GET  /api/executive-brief
POST /api/spr/plan                         GET  /api/commodities
GET  /api/cost-of-inaction                 GET  /api/backtest/events
GET  /api/backtest/{id}/replay             GET  /api/stress-test
POST /api/chat                             POST /api/integrations/slack
WS   /ws/feed
```

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

`backend/data/fixtures/*.json` (10 files): gdelt_events, vessels, sanctions, commodity_prices, india_imports, refineries, lng_terminals, critical_minerals, solar_imports, llm_responses, backtest_events. These are the demo's safety net. When adding a new endpoint that depends on a source, write a fixture in the same PR.

AIS spoofing near Iran is real. Do not claim 100% vessel attribution. PPAC, DGMS, MNRE data has a 30-45 day lag — flag scenario projections as such, not "today's" import figures.

## Reference docs

- `docs/architecture.md` — full system diagram, data-flow trace, scaling considerations
- `docs/architecture_diagram.md` — Mermaid + ASCII versions for the deck
- `docs/assumptions.md` — assumption ledger (numeric baselines, scenario parameters, what we don't model)
- `docs/demo_script.md` — 5-minute walkthrough with timing
- `docs/presentation_outline.md` — 10-slide deck outline
- `6a38ce305640d_ET_AI_Hackathon_2026_Problem_Statements.pdf` — PS2 is page 4-5
