# Resilience Grid

PS2 Energy Supply Chain Resilience for India — an AI-driven situational awareness and decision-support platform spanning crude oil, LNG, coking coal, critical minerals (lithium, cobalt, nickel, rare earths), and solar PV.

## Why this matters

India imports roughly 88 percent of its crude oil, with 40 to 45 percent of those barrels transiting the Strait of Hormuz. Around 50 percent of natural gas is imported as LNG, primarily from Qatar, the United States, the UAE, and Australia. Coking coal — the feedstock for primary steel — is about 85 percent imported, with around 70 percent sourced from Queensland and shipped through Malacca. Roughly 80 percent of solar PV modules and 60 percent of cells come from China, and over 90 percent of refined rare earths pass through Chinese processors. A single corridor incident or sanctions action can ripple across power, mobility, steel, and the clean-energy transition. This platform fuses vessel positions, geopolitical events, sanctions lists, and commodity prices into a unified risk picture and recommends concrete supply-chain hedges.

## What's in this repo

- `backend/` — FastAPI service, ingestion adapters, risk engine, LP optimiser, scenario simulator, Claude integration
  - `app/engines/` — risk_score, scenarios, spr_lp, sourcing
  - `app/llm/` — Claude prompt orchestration and summary synthesis
  - `app/ingest/` — PPAC, GIIGNL, AISStream, GDELT, OFAC, commodity-price adapters
- `frontend/` — React 18 + Vite + TypeScript dashboard
  - `src/views/` — Map, Corridors, Commodities, Scenarios, Briefing
  - `src/components/` — charts, alerts, panels
- `docs/` — `architecture.md`, `demo_script.md`, `data_sources.md`, `assumptions.md`
- `data/fixtures/` — pinned snapshots used when live APIs are unavailable in the demo
- `.env.example` — required environment variables

## Quickstart (Windows PowerShell)

Backend:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]
copy ..\.env.example .env
uvicorn app.main:app --reload --port 8000
```

Frontend (in a second terminal):

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 in a browser. The frontend proxies API calls to `http://localhost:8000`.

## Environment variables

Copy `.env.example` to `backend\.env` and fill in keys. The example file documents each variable; the required ones are:

- `ANTHROPIC_API_KEY` — Claude API access (uses `claude-opus-4-8` for synthesis, `claude-haiku-4-5-20251001` for high-frequency classification)
- `AISSTREAM_API_KEY` — vessel position websocket feed
- `GDELT_BASE_URL` — defaults to the public GDELT 2.0 endpoint
- `ALPHA_VANTAGE_API_KEY` — commodity price quotes
- `EIA_API_KEY` — US Energy Information Administration series
- `OFAC_SDN_URL`, `UN_SANCTIONS_URL`, `EU_SANCTIONS_URL` — sanctions list mirrors

If a key is absent the corresponding adapter falls back to `data/fixtures/*.json` and the API response is tagged `source: "fixture"`.

## Where the AI lives

- `backend/app/engines/risk_score.py` — corridor and commodity risk index from events, AIS density, sanctions exposure, and price volatility
- `backend/app/engines/scenarios.py` — what-if simulator for closures (Hormuz, Bab el-Mandeb, Malacca), sanctions tightening, weather, and Cape rerouting
- `backend/app/engines/spr_lp.py` — Strategic Petroleum Reserve drawdown and refill linear program over the Vizag, Mangalore, and Padur caverns
- `backend/app/engines/sourcing.py` — alternative-sourcing recommender for LNG cargoes, coking coal, and critical minerals under a disruption
- `backend/app/llm/summarise.py` — Claude-powered briefing generator that turns numeric outputs into an executive narrative with citations back to source events

## Demo flow (5 steps)

1. Open the **Map** view and point out live vessel density in the Strait of Hormuz alongside the corridor risk gauge.
2. Trigger the **Hormuz 14-day closure** scenario; watch corridor risk, crude price impact, and refinery utilisation update.
3. Switch to **Commodities** to show LNG, coking coal, and lithium exposure recomputing in parallel.
4. Run the **SPR LP** to draw down Vizag and Mangalore, then propose Russian Urals and US WTI substitution via **Sourcing**.
5. Generate the **Claude briefing** — a one-page narrative with linked GDELT events and sanctions citations, exportable as PDF.

The full narrated script is in `docs/demo_script.md`.

## Submission deliverables checklist

- [ ] Working backend at `http://localhost:8000` with `/docs` OpenAPI page
- [ ] Working frontend at `http://localhost:5173`
- [ ] `.env.example` with every required variable documented
- [ ] `docs/architecture.md` with the component diagram
- [ ] `docs/demo_script.md` with the 10-minute narrated walkthrough
- [ ] `docs/data_sources.md` listing PPAC, GIIGNL, AISStream, GDELT, OFAC, EIA, USGS, MNRE, World Bank
- [ ] `docs/assumptions.md` capturing every modelling assumption
- [ ] `data/fixtures/` with pinned snapshots so the demo runs offline
- [ ] Two-minute demo video linked from the submission form
- [ ] Slide deck (PDF) summarising problem, approach, architecture, impact

## License

Hackathon source code in this repository is released under the MIT License. Third-party data — PPAC bulletins, GIIGNL reports, GDELT events, AISStream vessel tracks, OFAC and UN sanctions lists, EIA series, USGS mineral commodity summaries, MNRE solar statistics, World Bank commodity prices — remains under the licenses of their respective providers and is used here only for non-commercial research and demonstration purposes.
