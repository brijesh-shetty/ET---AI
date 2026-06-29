# Architecture

## 1. System Overview

This system is a multi-commodity, signal-to-decision pipeline for India's strategic
energy and critical-materials supply chain. It ingests heterogeneous public signals
(geopolitical events, vessel movements, sanctions lists, commodity prices, regulatory
bulletins), normalizes them through per-commodity adapters, and computes a per-corridor
by per-commodity risk matrix. Scenario simulations, strategic-reserve linear programs,
and alternate-sourcing rankings are layered on top, and an LLM narrative engine
translates quantitative output into briefings, scenario explanations, and
recommendation drafts surfaced through a digital-twin dashboard.

## 2. High-Level Diagram

```
+------------------------------------------------------------------------------+
|                              SIGNAL LAYER                                    |
|  GDELT   AISStream   OFAC/UN/EU   EIA/AV   PPAC   GIIGNL   USGS   MNRE       |
+------+--------+---------+-----------+--------+--------+--------+-------------+
       |        |         |           |        |        |        |
       v        v         v           v        v        v        v
+------------------------------------------------------------------------------+
|                  PER-COMMODITY INGESTION ADAPTERS                            |
|   crude_oil   lng   coking_coal   crit_minerals   solar_pv   uranium         |
+------+-------------------+-------------------+--------------+----------------+
       |                   |                   |              |
       v                   v                   v              v
+------------------------------------------------------------------------------+
|                       RISK SCORING ENGINE                                    |
|     Matrix: corridors x commodities -> RiskScore [0..100]                    |
+------+-------------------+-------------------+--------------+----------------+
       |                   |                   |              |
       v                   v                   v              v
+----------------+   +------------------+   +------------------------------+
| Scenario       |   | SPR / Strategic  |   | Sourcing Intelligence        |
| Modeller       |   | Reserves LP      |   | (alternate suppliers, ports) |
+-------+--------+   +---------+--------+   +---------------+--------------+
        |                      |                            |
        +----------+-----------+-------------+--------------+
                   |                         |
                   v                         v
        +----------------------+   +---------------------------+
        | LLM Narrative Layer  |   | API Layer (FastAPI)       |
        | (Claude Opus/Haiku)  |   | REST + WS                 |
        +----------+-----------+   +-------------+-------------+
                   |                             |
                   +-------------+---------------+
                                 v
                 +----------------------------------+
                 |        DECISION DASHBOARD        |
                 |  Leaflet twin | Narrative feed   |
                 |  Scenario library | Charts       |
                 +----------------------------------+
```

## 3. Component Responsibilities

### 3.1 Signal Ingestion

- `gdelt_poller` — pulls 15-minute GDELT GKG slices, filters CAMEO event codes for
  conflict, port closure, sanctions, embargoes; geocodes to corridor polygons.
- `ais_consumer` — long-running WebSocket against AISStream.io. Filters by MMSI types
  (tanker, LNG carrier, bulker) and bounding boxes around the five tracked corridors.
- `ofac_snapshot` — daily SDN list pull plus EU and UN consolidated lists.
  Normalized to a single sanctions table keyed by entity name and IMO/MMSI.
- `eia_alpha_vantage` — Brent, WTI, Henry Hub, JKM, coking coal, lithium carbonate,
  polysilicon. Stored as time series for the volatility feature.
- `ppac_scraper` — monthly PPAC bulletin parser (PDF + HTML) for India crude and
  product import volumes by source country.
- `giignl_loader` — annual LNG trade flow tables, used as baseline source-country mix.
- `usgs_minerals` — USGS Mineral Commodity Summaries snapshot for lithium, cobalt,
  nickel, rare earths production shares.

### 3.2 Risk Scoring Engine

Computes a `RiskScore(corridor, commodity, t)` in `[0, 100]`. Pseudo-math:

```
event_pressure   = sum_i  w_event(type_i)   * decay(t - t_i)         for events on corridor
vessel_anomaly   = abs(density_t - density_baseline) / sigma_baseline
sanction_load    = count(sanctioned_entities active on corridor)
price_signal     = ewma_vol(price_commodity, span=14d)
import_exposure  = import_share(commodity, corridor)                 in [0,1]

raw  = a*event_pressure + b*vessel_anomaly + c*sanction_load + d*price_signal
score = 100 * sigmoid(raw) * import_exposure
```

Coefficients `a..d` are configured per commodity in `config/risk_weights.yaml`.
`import_exposure` gates the score: a corridor with high pressure but low dependence
for that commodity does not raise an alarm.

### 3.3 Scenario Modeller

Each scenario declares a primary commodity, the affected corridor(s), a duration,
and a set of shocks (closure probability, price multiplier, sanctions overlay).

| ID | Scenario | Primary Commodity | Corridor | Key Inputs |
|----|----------|-------------------|----------|------------|
| S1 | Hormuz Closure 14 d | Crude oil | Strait of Hormuz | closure_prob=0.7, brent_mult=1.35 |
| S2 | Red Sea Houthi Escalation | Crude + Container | Bab el-Mandeb | reroute_share=0.85, lead_time_add=14d |
| S3 | Queensland Coking Coal Strike | Coking coal | Malacca | export_drop=0.45, jkm_neutral |
| S4 | China Rare-Earth Export Curb | Rare earths | South China Sea | export_quota=0.5, price_mult=2.0 |
| S5 | Qatar LNG Outage | LNG | Hormuz + Suez | qatar_share_off=0.6, jkm_mult=1.6 |
| S6 | Kazakhstan Uranium Logistics Halt | Uranium | Caspian-Black Sea | shipment_delay=60d |
| S7 | Indonesia Nickel Export Ban Tightening | Nickel | Malacca | export_cut=0.3 |

### 3.4 SPR and Strategic Reserves LP

For a horizon `H` days and reserve sites `s in S` (Vizag, Mangalore, Padur for crude;
equivalent placeholders for LNG and minerals), decide daily withdrawal `x_{s,t}`
and import substitution `y_{r,t}` from alternate source `r`.

```
minimize    sum_t [ price_impact_t + lambda * reserve_drawdown_t ]
subject to  sum_s x_{s,t} + sum_r y_{r,t} + baseline_supply_t >= demand_t
            0 <= x_{s,t} <= max_withdraw_s
            sum_t x_{s,t} <= inventory_s
            sum_r y_{r,t} <= alt_supply_capacity_{r,t}
            reserve_drawdown_t = sum_s x_{s,t}
            price_impact_t = max(0, demand_t - baseline_supply_t - sum y) * elasticity
```

Solved with `scipy.optimize.linprog` (HiGHS) by default; PuLP fallback for richer
constraint sets. Output is a withdrawal schedule, residual price impact path, and a
shadow price per site interpreted as the marginal value of additional storage.

### 3.5 Sourcing Intelligence

Ranks alternate suppliers per commodity using a weighted score over:

- shipping distance from supplier port to nearest Indian terminal
- corridor risk for the route the shipment would take
- supplier political-risk index (configured per country)
- contractual flexibility flag (spot vs term-only)
- USD price delta vs incumbent

Top-N suppliers and recommended port-of-call are returned with confidence intervals.

### 3.6 Digital Twin

Leaflet map with composable layers:

- corridor polygons colored by current aggregate risk
- live vessel markers (tanker / LNG / bulker) clustered above 200 ships
- terminals: SPR sites, LNG regas (Dahej, Hazira, Kochi, Dabhol, Ennore), coking-coal
  ports (Paradip, Vizag, Dhamra), solar-module bonded warehouses
- refinery and steel-plant overlays
- a time slider that replays the last 72 h of risk evolution

### 3.7 LLM Narrative Layer

Three Claude prompt families:

- `risk_summary` (Haiku, `claude-haiku-4-5-20251001`) — fast, per-corridor 80-word
  status update refreshed every minute against the scoring engine output.
- `scenario_explanation` (Opus, `claude-opus-4-8`) — given the scenario inputs and
  LP outputs, generate a structured briefing with executive summary, quantitative
  impact, three options, and a recommended path.
- `recommendation_draft` (Opus) — produces a memo addressed to MoPNG / MoP / MEA with
  cited inputs. Citations are inline references to event IDs and dataset rows so the
  user can audit.

All prompts include a refusal contract: model must respond with a structured JSON
when confidence is below threshold so the UI can flag uncertainty.

### 3.8 API Layer

| Method | Path | Purpose |
|--------|------|---------|
| GET    | /api/health | Liveness |
| GET    | /api/commodities | List configured commodities |
| GET    | /api/corridors | List corridors and current aggregate risk |
| GET    | /api/risk/matrix | Full corridor x commodity risk matrix |
| GET    | /api/events?corridor= | Recent geopolitical events |
| GET    | /api/vessels?bbox= | Vessel snapshot in a bbox |
| POST   | /api/scenarios/run | Run a scenario, returns scenario_id |
| GET    | /api/scenarios/{id} | Scenario result with LP output and narrative |
| GET    | /api/sourcing?commodity= | Alternate sourcing ranking |
| GET    | /api/narrative/{corridor} | Latest LLM risk summary |
| WS     | /ws/risk | Live risk-matrix updates |
| WS     | /ws/vessels | Live vessel positions |

## 4. Data Flow

```
GDELT poller  ----> events_store  --+
AIS WS        ----> vessel_cache --+|
OFAC snapshot ----> sanctions_db -+||
Prices feed   ----> price_series -+||
                                  vvv
                          +----------------+
                          | risk_scorer    |
                          +-------+--------+
                                  |
                                  v
                          +----------------+        +----------------+
                          | risk_matrix    | <----- | config/weights |
                          +----+-----+-----+        +----------------+
                               |     |
              +----------------+     +---------------+
              v                                      v
   +---------------------+               +-----------------------+
   | scenario_modeller   |               | digital_twin renderer |
   +----------+----------+               +-----------------------+
              |
              v
   +---------------------+
   | spr_lp solver       |
   +----------+----------+
              |
              v
   +---------------------+         +----------------------+
   | sourcing_intel      | ------> | llm_narrative (Opus) |
   +---------------------+         +----------+-----------+
                                              |
                                              v
                                       /api/scenarios/{id}
```

Density-anomaly detection runs on a 5-minute window over `vessel_cache` and emits
synthetic events into `events_store` so unusual loitering at chokepoints feeds the
same scoring path as GDELT-sourced events.

## 5. Multi-Commodity Coverage Matrix

| Commodity | Primary Source(s) | Primary Corridor | Fixture File | Live API Note |
|-----------|-------------------|------------------|--------------|---------------|
| Crude oil | Saudi, Iraq, UAE, US, Russia | Hormuz, Bab el-Mandeb | data/fixtures/crude_imports.json | PPAC bulletin scraper; EIA Brent |
| LNG | Qatar, US, UAE, Australia | Hormuz, Suez | data/fixtures/lng_flows.json | GIIGNL annual + JKM via Alpha Vantage |
| Coking coal | Australia (QLD) | Malacca | data/fixtures/coking_coal.json | Ministry of Steel monthly; spot via AV |
| Lithium | Chile, Argentina, China | South China Sea | data/fixtures/lithium.json | USGS annual snapshot |
| Cobalt | DRC via CN refiners | Cape / Suez | data/fixtures/cobalt.json | USGS + OFAC overlays |
| Nickel | Indonesia, Philippines | Malacca | data/fixtures/nickel.json | USGS annual; LME via AV |
| Rare earths | China (~90%) | South China Sea | data/fixtures/rare_earths.json | USGS; no reliable live spot |
| Solar PV (modules + cells) | China | South China Sea | data/fixtures/solar_pv.json | MNRE monthly; BloombergNEF proxy |
| Uranium | Kazakhstan, Russia, France | Caspian-Black Sea | data/fixtures/uranium.json | DAE annual; no public spot WS |
| LPG / ATF | Saudi, UAE, US | Hormuz | data/fixtures/petro_products.json | PPAC monthly |

Default runtime mode is fixture-backed. Each adapter exposes a `live=True` switch
that is no-op unless the matching API key is present in env.

## 6. Tech Choices and Rationale

- FastAPI for async-first ingestion and WebSocket fan-out.
- pandas + pydantic for typed in-memory tables; avoids a DB in the scaffold.
- scipy HiGHS for LP since it is in-tree and fast for the sizes here; PuLP kept as a
  fallback when the model needs integer variables.
- httpx for HTTP because both sync and async share one client.
- React + Vite + TypeScript for fast HMR and typed props at the component boundary.
- Leaflet over Mapbox to avoid a token requirement at the hackathon table.
- Recharts for charts because it composes with React state directly.
- Tailwind with a constrained palette (slate-900 base, indigo-500 accent, amber and
  red for alert states) to keep design decisions out of the critical path.
- Claude Opus for synthesis where reasoning depth matters, Haiku for the
  high-frequency per-corridor summaries where latency dominates.

## 7. Scalability

Corridors, commodities, sources, and risk weights are declared in `config/*.yaml`.
Adding a new commodity is a YAML edit plus a fixture file; the adapter, scoring
matrix column, dashboard tile, and scenario inputs auto-extend. The risk engine
processes commodities in parallel via `asyncio.gather` and short-circuits on
configurable `import_exposure` thresholds. AIS handling uses a per-corridor consumer
so each chokepoint scales independently.

## 8. Security

- All third-party keys are read from environment variables, never checked in.
- No PII is stored. Vessel data is public AIS; sanctions data is public.
- The default mode is fixture-backed so the system runs offline at a demo table.
- LLM prompts include a strict no-tool-call contract; the API never forwards user
  free-text to Claude without a validated schema wrapper.
- CORS is locked to the local Vite origin in dev; production builds disable it.

## 9. Local-Dev Topology

```
+--------------------+         +--------------------+
| React (Vite :5173) | <-----> | FastAPI (:8000)    |
+--------------------+   REST  +---------+----------+
        ^                                |
        |  WS /ws/risk, /ws/vessels      |
        +--------------------------------+
                                         |
                                         v
                                +--------------------+
                                | in-process stores  |
                                | (pandas, dicts)    |
                                +--------------------+
                                         |
                                         v
                                +--------------------+
                                | data/fixtures/*    |
                                +--------------------+
```

Start order in development: `uvicorn backend.app:app --reload` then
`npm run dev` in `frontend/`. Both processes are independent; the frontend falls
back to fixtures if the backend is not reachable so the dashboard always renders.

## 10. Production Notes

For a real deployment the following would change:

- Replace the in-process stores with Postgres for relational data
  (events, sanctions, scenario runs) and Redis for the vessel cache and pub/sub
  channels that today are in-memory.
- Move fixture JSON to S3 with versioned object keys; adapters point at S3 by env.
- Add an authn layer (OIDC against a government SSO) and per-role RBAC, so an
  analyst can run scenarios but only an authorized officer can mark a
  recommendation as adopted.
- Move the LP solver behind a queue (Celery + Redis or AWS Batch) since real
  scenarios over 90-day horizons with stochastic shocks dominate request latency.
- Promote the AIS consumer to a dedicated worker with backpressure and replay from
  Kafka; the dashboard subscribes via a thin WebSocket gateway.
- Add observability: OpenTelemetry traces across adapters, scoring, and LLM calls;
  per-prompt token accounting; cost dashboards for Claude usage.
- Audit logging for every recommendation draft and every scenario run, since
  outputs may inform real procurement and reserve actions.
