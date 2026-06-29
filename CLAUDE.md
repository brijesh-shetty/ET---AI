# ET AI Hackathon 2026 — PS2: Energy Supply Chain Resilience

## Project goal

Build an AI-powered Supply Chain Resilience system for India that monitors all strategic energy and material imports — crude oil, LNG, coking coal, critical minerals (lithium, cobalt, nickel, rare earths), solar PV, and uranium — across geopolitical and logistics risk continuously, models multi-commodity disruption scenarios, and generates executable procurement signals. Submission for ET AI Hackathon 2026.

Deliverables required: working prototype, architecture diagram, presentation deck, demo video.

## Problem statement summary

India imports ~88% of its crude oil with 40-45% transiting the Strait of Hormuz, and its Strategic Petroleum Reserves at Vizag, Mangalore and Padur cover only ~9.5 days of consumption. But crude is just one front. India imports ~50% of its natural gas as LNG (Qatar, US, UAE, Australia via terminals at Dahej, Hazira, Kochi, Dabhol, Ennore); ~85% of its coking coal — about 70% from Queensland, Australia via Paradip, Vizag and Dhamra — which directly drives steel sector margins; ~90% of its rare earth needs from China; lithium, cobalt and nickel supply chains dominated by China-Chile-DRC-Indonesia; ~80% of solar modules and ~60% of solar cells from China; and uranium from Kazakhstan, Russia and France.

Geopolitical events (US-Iran 2025 standoff, Red Sea Houthi attacks, Iran sanctions, China export controls on rare earths and gallium, Indonesia nickel export policy shifts, Queensland weather) repeatedly stress-test these exposures. Existing supply chain tools are reactive, single-commodity, and cannot model multi-corridor geopolitical scenarios in real time.

The gap: there is no intelligence layer that fuses news, vessel tracking, sanctions, and commodity signals across the full import basket into live disruption scores and procurement recommendations.

## Scope decisions

Five components are listed in the problem statement. We are not building all five equally, and we extend each to multi-commodity coverage where the data supports it.

**Build deep (hero modules):**
- Geopolitical Risk Intelligence Agent — live disruption score per corridor (Hormuz, Bab el-Mandeb / Red Sea, Malacca, South China Sea, Cape of Good Hope) and per supplier country, covering crude, LNG, coal, minerals and solar.
- Disruption Scenario Modeller — Hormuz closure (crude + LNG), Red Sea suspension (crude + container + LNG), Queensland coal export shock, China rare-earth export curb, Indonesia nickel restriction.
- Supply Chain Digital Twin — geospatial map of source countries to Indian ports / refineries / LNG terminals / steel mills / battery and solar assembly hubs, with live AIS overlay.

**Build credibly (supporting modules):**
- Strategic Reserve Optimisation Agent — linear programming model for SPR drawdown (crude). Coking coal stockpile heuristic and LNG inventory days-of-cover indicators sit alongside but are not full LPs.

**Build minimal (scope-controlled):**
- Adaptive Procurement Orchestrator — positioned as "sourcing intelligence" not refinery-grade or smelter-grade optimisation. We do not claim grade-specific crude, coal washability, lithium chemistry, or rare-earth separation knowledge without a domain mentor.

The reason this matters: judges with industry expertise will probe the procurement module. Overclaiming there will hurt more than scoping down. Multi-commodity breadth is our differentiation; depth claims stay honest.

| Module | Crude | LNG | Coking coal | Critical minerals | Solar PV | Uranium |
|--------|-------|-----|-------------|-------------------|----------|---------|
| Risk score | Deep | Deep | Deep | Medium | Medium | Light |
| Scenario modeller | Deep | Deep | Deep | Medium | Medium | Light |
| Digital twin | Deep | Deep | Deep | Medium | Medium | Light |
| SPR / reserve LP | Deep (LP) | Days-of-cover | Stockpile heuristic | Out | Out | Out |
| Sourcing intelligence | Medium | Medium | Medium | Medium | Medium | Light |

## Architecture

```
                External signals (real-time, multi-commodity)
                                    |
   +---------+---------+---------+---------+---------+---------+
   | GDELT   | AIS     | OFAC/UN | EIA /   | PPAC    | USGS /  |
   | events  | Stream  | EU      | AlphaV. | India   | GIIGNL  |
   | (news)  | (vessel)| (sanct.)| (price) | (oil/gas)| (LNG/mins)|
   +---------+---------+---------+---------+---------+---------+
        |         |         |         |         |         |
        v         v         v         v         v         v
   +-------------------------------------------------------------+
   |              Ingestion layer (per commodity)                |
   |   ingest/gdelt.py  ais.py  sanctions.py  eia.py             |
   |   ingest/lng.py    coal.py minerals.py   solar.py           |
   +-------------------------------------------------------------+
                                    |
                                    v
                    +---------------------------------+
                    |   Geopolitical Risk Engine      |
                    |   per-corridor disruption score |
                    |   (Hormuz / BabM / Malacca /    |
                    |    SCS / Cape) 0-100            |
                    |   per-commodity weighting       |
                    +---------------------------------+
                                    |
            +----------+-------------+-------------+----------+
            |          |             |             |          |
        Scenario   Digital twin   SPR LP        Stockpile  Sourcing
        modeller   map + AIS      (crude)       heuristic  intelligence
        (Hormuz,   (ports,        Days-of-      (coal,     (top-3
        Red Sea,   refineries,    cover         LNG)       alt. suppliers
        QLD coal,  LNG terms,     (LNG, coal)              by commodity)
        REE curb)  steel mills,
                   solar fabs)
            +----------+-------------+-------------+----------+
                                    |
                                    v
                       Decision dashboard
                       (multi-commodity ticker,
                        scenarios, recommendations,
                        evidence trail)
```

## Tech stack

- Backend: Python 3.11, FastAPI, async, pandas, pydantic, scipy / PuLP for LP, httpx for HTTP, websockets for AIS.
- Frontend: React 18, Vite, TypeScript, Tailwind CSS, Leaflet for maps, Recharts for charts, axios.
- LLM: Claude API. `claude-opus-4-8` for synthesis and recommendation drafting, `claude-haiku-4-5-20251001` for high-frequency news classification.
- ML: scikit-learn for the disruption score model, PuLP / scipy.optimize for the SPR LP.
- Tailwind theme: neutral grays plus indigo-500 accent; amber/red for alert states; slate-900 background.

## Data sources

All sources are free or have a sufficient free tier for hackathon use. India coverage verified.

| Source | What | Commodities | Access | Real-time | Notes |
|--------|------|-------------|--------|-----------|-------|
| GDELT | Geopolitical news events, CAMEO codes | All | Free REST + GKG, 15 min cadence | Yes | Primary signal for the disruption engine |
| AISStream.io | Real-time vessel AIS positions | Crude, LNG, coal, container | Free WebSocket with signup | Yes | Hormuz, Red Sea, Malacca, SCS focus |
| OFAC SDN / UN / EU sanctions | Sanctions registries | All | Free JSON/XML download | Daily | Cross-reference vessel owners, refiners, miners |
| EIA Open Data | US energy admin global data | Crude, LNG, coal | Free API with key | Daily | Brent / WTI / Henry Hub / API2 references |
| Alpha Vantage | Commodity and FX prices | Crude, gas, base metals | Free tier with key | Daily | Backup price feed |
| World Bank Commodities | Global commodity prices | All | Free monthly CSV | Monthly | Trend baseline |
| PPAC India | Crude imports and refinery dispatches by source | Crude, LPG, ATF | Free monthly bulletin | Monthly lag | India-specific consumption and refinery data |
| Petroleum Ministry / PPAC monthly | Natural gas and LNG imports | LNG | Free monthly bulletin | Monthly lag | Terminal-wise regas dispatch |
| GIIGNL Annual Report | Global LNG trade flows | LNG | Free PDF | Annual | Source-country share baseline |
| DGMS, Ministry of Steel | Coking coal imports, steel production | Coking coal | Free monthly | Monthly | India coal import by source |
| World Steel Association | Global steel output, scrap flows | Coking coal | Free monthly | Monthly | Demand-side baseline for coal scenarios |
| Australian export stats (ABS) | Queensland coal export volumes | Coking coal | Free monthly | Monthly | Source-side signal |
| USGS Mineral Commodity Summaries | Reserves, production, trade | Lithium, cobalt, nickel, REE | Free PDF / CSV | Annual | Authoritative baseline |
| S&P Global Commodity Insights headlines | Mineral price moves | Minerals | Headlines only free | Daily | Trend signal, not live spot |
| Ministry of Mines India | Domestic mineral output and imports | Minerals | Free monthly | Monthly | India-specific |
| BloombergNEF headlines | Solar PV module and cell prices | Solar | Headlines only free | Weekly | Trend signal |
| MNRE | India solar installations and module imports | Solar | Free monthly | Monthly | India-specific demand |
| China customs export data | Module / cell / REE / gallium export volumes | Solar, REE | Free monthly (GACC) | Monthly | Source-side signal |
| WNA / IAEA | Uranium production and trade | Uranium | Free annual | Annual | Baseline only |
| NewsAPI | Headline news fallback | All | Free 100/day | Real-time | Supplements GDELT for LLM summaries |
| OpenStreetMap | Ports, pipelines, refinery / terminal / mill polygons | All | Overpass API, free | Static | Base layer for the digital twin |
| Baltic Exchange BDTI / BCI | Tanker and dry bulk rate indices | Crude, coal | Headlines only free | Daily | Weak link — do not claim live spot rates |

Documented data caveats:
- AIS data near Iran and parts of the Red Sea can be intentionally spoofed by sanctioned tankers. Do not claim 100% vessel attribution.
- PPAC, DGMS, MNRE, and Ministry of Mines data is monthly. For live demo, use scenario-driven projections, not "today's" import figures.
- Spot prices for tanker rates, REE oxides, lithium carbonate and PV modules behind paywalls (Argus, Fastmarkets, S&P, BloombergNEF) — use trade press headline numbers; do not pretend to have live spot rate access.
- China customs (GACC) export data has a 4-6 week lag and product code aggregation issues for solar and REE — treat as trend signal.

## Project structure (target)

```
D:\ET AI Hackathon\
  CLAUDE.md                       <- this file
  6a38ce305640d_ET_AI_Hackathon_2026_Problem_Statements.pdf
  README.md
  .env.example                    <- API keys: ANTHROPIC, AISSTREAM, NEWSAPI, EIA, ALPHAVANTAGE
  backend/
    pyproject.toml
    app/
      main.py                     <- FastAPI entrypoint
      ingest/
        gdelt.py                  <- GDELT poller (every 15 min, multi-commodity keywords)
        ais.py                    <- AISStream WebSocket consumer (Hormuz, Red Sea, Malacca, SCS)
        sanctions.py              <- OFAC / UN / EU SDN snapshot loader
        eia.py                    <- crude / gas / coal price client
        lng.py                    <- GIIGNL + PPAC LNG dispatch ingest
        coal.py                   <- DGMS + Australian export stats + World Steel ingest
        minerals.py               <- USGS + Ministry of Mines + China customs (REE, Li, Co, Ni)
        solar.py                  <- MNRE + China customs PV exports
      engines/
        risk_score.py             <- per-corridor disruption score, multi-commodity weighting
        scenarios.py              <- Hormuz / OPEC / Red Sea / QLD coal / REE curb / Indonesia Ni
        spr_lp.py                 <- strategic crude reserve linear program
        coal_stockpile.py         <- coking coal stockpile days-of-cover heuristic
        lng_cover.py              <- LNG terminal days-of-cover indicator
        sourcing.py               <- alternative supplier ranking per commodity (scoped)
      api/
        routes.py                 <- /score, /scenarios/{name}, /twin/state, /commodity/{c}
      llm/
        summarise.py              <- Claude calls for narrative output
    data/
      fixtures/                   <- JSON fixtures used when live API not feasible in scaffold
    tests/
  frontend/
    package.json
    src/
      pages/
        Dashboard.tsx
        DigitalTwin.tsx
        ScenarioRun.tsx
      components/
        RiskTicker.tsx
        VesselMap.tsx
        ScenarioCard.tsx
        CommoditySwitcher.tsx
      lib/
        api.ts
  docs/
    architecture.md
    demo_script.md
    assumptions.md                <- explicit assumption ledger (judges will probe)
```

## Build phases

**Phase 1 — signal ingestion (Day 1)**
- GDELT poller pulling Hormuz, Red Sea, Persian Gulf, Malacca, South China Sea, Queensland events with per-commodity keyword sets.
- AISStream WebSocket reading vessel density in target corridors, classified by ship type (tanker / LNG carrier / bulker / container).
- OFAC / UN / EU sanctions snapshot loader.
- Commodity baselines: PPAC (crude, LNG), DGMS (coal), USGS + Ministry of Mines (minerals), MNRE + China customs (solar). Where live API is not feasible in the scaffold, load from `data/fixtures/*.json`.

**Phase 2 — risk engine (Day 1-2)**
- Per-corridor disruption score (0-100) updated every 15 min, with per-commodity weights (Hormuz weights crude and LNG high; Malacca weights coal and minerals high; SCS weights solar and REE).
- LLM summarises top 3 signals driving today's score per commodity.
- API endpoints serving live scores plus narrative.

**Phase 3 — scenario modeller (Day 2)**
- Named scenarios across the basket: Hormuz partial closure (crude + LNG), Red Sea full suspension (crude + container + LNG via Cape reroute), Queensland coal export shock (steel margin compression), China rare-earth and gallium export curb (EV battery and electronics), Indonesia nickel export restriction (battery and stainless).
- Each computes cascading impact on Indian refineries, LNG terminal dispatch, steel mill input cost, EV battery cell cost, solar module landed cost, and reserve depletion timelines.
- All assumptions logged in `docs/assumptions.md`.

**Phase 4 — digital twin + SPR LP (Day 2-3)**
- Leaflet map: source countries, multi-corridor AIS overlay, Indian crude refineries, LNG terminals, coking coal ports, lithium-cell / battery-pack assembly hubs, solar fabs.
- Click a corridor or supplier country to trigger the relevant scenario animation.
- SPR LP runs alongside for crude; coking coal stockpile heuristic and LNG days-of-cover indicators render as Gantt-style strips for the non-LP commodities.

**Phase 5 — decision dashboard + demo polish (Day 3)**
- Single-pane glass view: live multi-commodity score ticker, scenario library, map, reserve / stockpile plans, sourcing recommendations.
- Narrative LLM output for each recommendation.
- Recorded demo video, slide deck, architecture diagram.

## Evaluation criteria mapping (judges' rubric)

| Criterion | Weight | How we score |
|-----------|--------|--------------|
| Innovation | 25% | Most teams will scope PS2 to crude only. Live multi-commodity coverage — crude, LNG, coking coal, critical minerals, solar — across five corridors, fused into one risk engine, is a rare differentiator. |
| Business Impact | 25% | National security exposure spans $15B+/day GDP from energy alone, plus steel ($150B+ sector), EV and electronics inputs, and the $20B+/year solar build-out. Cite the McKinsey 47-day stabilisation gap for crude. |
| Technical Excellence | 20% | Multi-agent design, real APIs not synthetic data where feasible, explicit per-commodity scenario assumptions, validated LP for crude SPR, transparent fall-back to fixtures for monthly-cadence sources. |
| Scalability | 15% | Architecture supports adding commodities, corridors, suppliers, and Indian processing facilities through configuration. Ingestion modules follow a uniform interface. |
| User Experience | 15% | Digital twin map is the hero. Multi-commodity ticker + clickable corridors + LLM-generated narrative makes complex cross-sector data legible to a procurement director, steel CFO, EV-OEM strategist or policymaker. |

## Demo script (target — 5 min)

1. Opening (30s): India's exposure is not just crude. It is crude plus LNG plus coking coal plus rare earths plus solar — and they share corridors. We built one intelligence layer for the whole basket.
2. Live dashboard (60s): show today's corridor scores. Hormuz amber (crude + LNG), Malacca yellow (coal + minerals), South China Sea yellow (solar + REE). Narrative cites GDELT events from last 24h per commodity.
3. Trigger scenario A — Hormuz click (75s): click Strait of Hormuz. Map animates the cascade: crude tankers reroute via Cape, LNG carriers from Qatar diverted, Dahej and Hazira regas dispatch falls, refinery throughput drops, fuel price curve rises, SPR depletion accelerates.
4. Trigger scenario B — Queensland click (45s): click Queensland coal port. Coking coal price spikes, Paradip and Vizag landed cost rises, JSW / SAIL / Tata Steel input cost band widens on the steel-margin strip.
5. Trigger scenario C — rare-earth chokepoint click (45s): click China REE / gallium hub. EV battery and electronics input cost rises, solar module landed cost moves; sourcing module shows the top alternates (Australia for Li, Indonesia for Ni, Vietnam fab for cells) with explicit caveats on China's ~90% refining oligopoly.
6. SPR + reserve plan (45s): crude SPR LP outputs the optimal drawdown Gantt. Coking coal stockpile and LNG cover strips render alongside. Show the trade-off — early draw stabilises prices but exhausts the buffer faster.
7. Close (30s): one-line statement of the gap we close (multi-commodity, multi-corridor real-time intelligence) and the next step (refinery / mill / fab dispatch integration with industry partners).

## Hard constraints and gotchas

- Never claim to know which crude grades each Indian refinery can process. We do not have that data. The Procurement Orchestrator must be framed as "sourcing intelligence" not "refinery optimisation".
- LNG terminal regasification constraints (slot scheduling, send-out capacity, ambient-temperature derates) are not modelled. The LNG days-of-cover indicator assumes nameplate dispatch.
- Coking coal grade differentiation (hard coking, semi-soft, PCI, washability, sulphur, CSR) is not modelled. We treat coking coal as a single aggregate; do not claim grade-specific blend optimisation.
- Rare earth processing is an oligopoly: China controls ~90% of separation and refining capacity. We acknowledge this openly. Sourcing recommendations for REE point to mined sources, not refined oxide capacity, and we say so on screen.
- Critical mineral chemistry (lithium hydroxide vs carbonate, NMC vs LFP cathode implications, cobalt sulphate vs metal) is not modelled. Sourcing is at the element level only.
- Solar PV module efficiency, bifaciality, TOPCon vs HJT premium and degradation curves are not modelled. Pricing uses headline c/W trend signal only.
- Always show assumptions on screen during scenario playback. Judges will probe.
- AIS spoofing near Iran and parts of the Red Sea is real. Acknowledge it. Do not claim 100% vessel attribution.
- Tanker (BDTI / BDTI) and dry bulk (BCI) rate spot data is paid. Use headline numbers from trade press; do not fake live spot rates.
- China customs (GACC) data has a 4-6 week lag and product-code aggregation issues for solar and REE. Treat as trend, not a live signal.
- GDELT timestamps are UTC. Convert to IST for display.
- Hackathon Anthropic API key has rate limits. Cache LLM responses for repeated demo runs.

## Commands

```powershell
# Backend (PowerShell)
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev

# Pipeline (one-shot ingest test)
python -m app.ingest.gdelt --since 24h
python -m app.ingest.sanctions --refresh
```

## Reference documents

- Problem statement PDF: `6a38ce305640d_ET_AI_Hackathon_2026_Problem_Statements.pdf` (page 4-5)
- Assumption ledger: `docs/assumptions.md` (single source of truth for what we assume and why)
- Demo script: `docs/demo_script.md`

## Team and timeline

- Hackathon date: 2026-06-28
- Team size: TBD (fill in when known)
- Submission: working prototype + architecture diagram + presentation deck + demo video
