# Assumption Ledger

## 1. Why this document exists

Hackathon judges will probe modeling assumptions before accepting any decision-support output. This ledger makes every numeric input, weight, and exclusion explicit, attributable to a public source, and revisable through configuration. Nothing in the platform is meant to be opaque: if a number drives a recommendation, it is listed here with the source and a path to override it.

---

## 2. Commodity baselines

All baselines reflect FY24-FY25 reporting unless noted. Values are stored in `data/fixtures/commodity_baselines.json` and surfaced read-only in the UI.

### 2.1 Crude oil

| Field | Value | Source |
|---|---|---|
| Total imports | ~4.8 MMb/d | PPAC monthly bulletin, FY25 |
| Hormuz transit share | 40-45% | PPAC origin tables, IEA Oil Market Report |
| Top suppliers | Iraq, Saudi Arabia, Russia, UAE, US | PPAC |
| SPR total capacity | 39.0 MMb (5.33 MMt) | ISPRL public disclosures |
| Vizag SPR | 1.33 MMt | ISPRL |
| Mangalore SPR | 1.50 MMt | ISPRL |
| Padur SPR | 2.50 MMt | ISPRL |
| Consumption cover | ~9.5 days at current run rate | Derived: SPR / refinery throughput |

### 2.2 LNG / natural gas

| Field | Value | Source |
|---|---|---|
| Total LNG imports | ~30 MTPA | PPAC, GIIGNL Annual Report |
| Qatar share | ~40% | GIIGNL, PPAC |
| US share | ~15% | GIIGNL |
| UAE share | ~10% | GIIGNL |
| Russia share | ~5% | GIIGNL |
| Dahej regas capacity | 17.5 MTPA | Petronet LNG |
| Hazira | 5.0 MTPA | Shell India |
| Kochi | 5.0 MTPA | Petronet LNG |
| Dabhol | 5.0 MTPA | Konkan LNG |
| Ennore | 5.0 MTPA | IOCL |

### 2.3 Coking coal

| Field | Value | Source |
|---|---|---|
| Total imports | ~70 MTPA | Ministry of Steel, DGMS |
| Australia (Queensland) | ~70% | Ministry of Steel |
| Other origins | US, Indonesia, Mozambique | Ministry of Steel |
| Dependent steel capacity | ~120 MTPA crude steel | Ministry of Steel |
| Receiving ports | Paradip, Visakhapatnam, Dhamra | Major Ports Authority |

### 2.4 Critical minerals

| Mineral | Import dependence | Refining concentration | Source |
|---|---|---|---|
| Lithium | ~100% | China ~60% of global refining | USGS MCS, IEA Critical Minerals Outlook |
| Cobalt | ~70% | China ~70% of refining; DRC ~70% of mining | USGS MCS |
| Nickel | ~80% | Indonesia/Philippines for mine output | USGS MCS |
| Rare earths | ~85% | China ~90% of separation | USGS MCS, IEA |

### 2.5 Solar PV

| Field | Value | Source |
|---|---|---|
| Module import share | ~80% from China | MNRE, DGCIS |
| Cell import share | ~60% from China | MNRE |
| FY24 capacity addition | ~13 GW | MNRE annual report |
| Imported value share | ~80% of installed value | MNRE, industry estimates |

### 2.6 Uranium

| Field | Value | Source |
|---|---|---|
| Domestic source | Jaduguda (limited) | DAE annual report |
| Kazakhstan share of imports | ~30% | DAE, IAEA |
| Other origins | Russia, France | DAE, IAEA |

---

## 3. Risk score formula

Per corridor x commodity pair, the composite score is:

```
risk = w_geo * geo_signal
     + w_ais * ais_anomaly
     + w_sanctions * sanctions_signal
     + w_price * price_vol
```

Default weights (defined in `backend/config/weights.yaml`, hot-reloadable):

| Component | Weight | Driver |
|---|---|---|
| `geo_signal` | 0.40 | GDELT event tone + count for corridor geography |
| `ais_anomaly` | 0.25 | Vessel drift, dark gaps, rerouting vs 90-day baseline |
| `sanctions_signal` | 0.15 | New OFAC/UN/EU listings touching counterparties on the route |
| `price_vol` | 0.20 | 10-day realized vol of front-month benchmark |

Each component is clipped to [0, 1] before the weighted sum, so the composite is bounded in [0, 100] after multiplying by 100.

Threshold bands:

| Band | Range | Color |
|---|---|---|
| Low | < 30 | green |
| Elevated | 30 - 55 | amber |
| High | 55 - 75 | orange |
| Critical | > 75 | red |

---

## 4. Scenario parameters

Each scenario is defined in the `SCENARIOS` dict in `backend/app/engines/scenarios.py` (price/GDP/SPR elasticities) and is referenced from the UI scenario panel. The served projection is computed in `_project_impact()` in `backend/app/api/routes.py`, which reads those same documented elasticities. Parameters listed here are the defaults; users can override intensity and duration before running.

### 4.1 Hormuz partial closure

| Parameter | Default |
|---|---|
| Throughput reduction | 50% |
| Duration | 14 days |
| Brent shock | +30% |
| Affected commodities | Crude, LNG (Qatar) |

### 4.2 OPEC+ emergency cut

| Parameter | Default |
|---|---|
| Supply removed | 1.0 MMb/d |
| Brent shock | +15% |
| Duration | 90 days |

### 4.3 Red Sea full suspension

| Parameter | Default |
|---|---|
| Reroute | Cape of Good Hope |
| Added transit | +18 days |
| LNG price | +12% |
| Container freight | +25% |

### 4.4 Australian coking coal disruption

| Parameter | Default |
|---|---|
| Trigger | Cyclone or port strike, Queensland |
| Queensland export shock | -30% |
| Coking coal price | +25% |
| Downstream effect | Steel mill margin compression |

### 4.5 China rare earth export curbs

| Parameter | Default |
|---|---|
| NdFeB magnet supply | -50% |
| Affected sectors | EV traction motors, wind turbines, defence |

### 4.6 China solar module export tariff retaliation

| Parameter | Default |
|---|---|
| Project IRR delta | -200 bps |
| BCD effectiveness short-term | low |

### 4.7 Kazakhstan uranium disruption

| Parameter | Default |
|---|---|
| NPCIL fuel buffer | ~6 months |
| Alternative path | Cameco (Canada) contracting |

### 4.8 Sector transmission (refinery run-rate & power-sector stress)

The PS requires each scenario to project **refinery run rates** and **power-sector stress** alongside price and GDP. These are *mechanism-driven*, not a function of the intensity slider alone — `SCENARIO_SECTOR_TRANSMISSION` in `routes.py` sets the maximum deflection at full intensity, scaled by intensity × duration × within-window ramp. Key modelling choices:

- **Only crude/LNG (refinery feedstock) shocks cut refinery run rates.** Coking coal feeds *steel*, not refineries; rare earth / solar / uranium do not touch refineries → run-rate stays at 100%.
- **Power stress is driven by gas-for-power (LNG) and grid-fuel shortfalls.** Coking coal is *metallurgical, not thermal* → negligible power impact. Uranium feeds nuclear (~3% of generation) behind an ~18-month fuel buffer → small and slow.

| Scenario | Refinery run-rate drop (pp, at full) | Power-stress rise (index pts, at full) |
|---|---|---|
| Hormuz partial closure | 22 | 28 |
| OPEC+ emergency cut | 8 | 6 |
| Red Sea suspension | 5 | 8 |
| Australian coking coal | 0 | 2 |
| China rare earth curbs | 0 | 3 |
| China solar tariff | 0 | 4 |
| Kazakhstan uranium | 0 | 6 |

GDP drag is likewise routed through each scenario's **own** channel (Brent→import-bill for oil scenarios; steel-margin for coking coal; EV/wind capex for rare earth; renewable capex for solar; NPP capex for uranium) rather than a single oil-price proxy, so non-oil scenarios register a non-zero, defensible GDP impact. Baselines: refinery run rate 100%, power-stress index 20, diesel ₹92/L, GDP trend 6.5%.

---

## 5. SPR linear program

Decision variables, per day `t` in horizon `T`:

- `drawdown_t` >= 0, barrels released from SPR
- `replenish_t` >= 0, barrels injected into SPR

Objective:

```
minimize  sum_{t=1..T}  price_impact( deficit_t )
```

Subject to:

```
SPR_t            = SPR_{t-1} - drawdown_t + replenish_t
consumption_t    - imports_t = drawdown_t - inventory_change_t
SPR_t            >= 0
drawdown_t       <= max_injection_rate
replenish_t      <= max_injection_rate
```

Solved with PuLP CBC. `price_impact` is a piecewise-linear function of `deficit_t` calibrated from historical Brent moves during the 2019 Abqaiq strike and the 2022 Russia diversion. The calibration table lives in `backend/lp/price_impact.json`.

---

## 6. Sourcing module — exclusions

The sourcing optimizer is intentionally narrow. It does NOT model:

- Refinery configuration or crude grade chemistry (no slate optimization)
- Pipeline hydraulics (line-fill, batching, drag-reducing agents)
- Live tanker spot rates (we ingest Baltic Exchange BDTI headlines only)
- Long-term contract terms (all supply is treated as spot for tractability)
- Port-specific draft restrictions or berth queueing

These omissions are deliberate. Judges should treat sourcing output as a shortlist for procurement review, not a final allocation.

---

## 7. Data freshness

| Feed | Cadence | Lag |
|---|---|---|
| GDELT events | 15 min | < 30 min |
| AIS vessel positions | live WebSocket | seconds |
| OFAC SDN | daily refresh | 24 h |
| UN / EU sanctions | daily refresh | 24 h |
| Commodity prices (Brent, JKM, coking coal, lithium carbonate) | daily close | end of day |
| PPAC monthly bulletin | monthly | 30-45 day lag |
| GIIGNL World LNG Report | annual | up to 12 months |
| USGS Mineral Commodity Summaries | annual | up to 12 months |

The UI surfaces a "Data freshness" badge per feed so users see which inputs are stale before relying on them.

---

## 8. AIS spoofing acknowledgement

Vessels operating near Iran, sanctioned Russian terminals, and parts of the Red Sea routinely broadcast false GNSS positions, switch transponders off ("dark gaps"), or borrow another vessel's MMSI. We:

- Flag dark gaps over 6 hours as anomalies but do NOT auto-conclude sanctions evasion.
- Do NOT claim 100% attribution of any vessel to any cargo or owner.
- Cross-check positions against scheduled port calls where data exists.

---

## 9. Score interpretation guide

For both users and judges:

- The composite score is a triage signal, not a forecast. It says "look here today," not "this will close."
- An "elevated" reading does not predict a closure. It tells procurement and logistics teams to review the alternative options the system has surfaced.
- "Critical" should trigger a human decision review, not an automated action.
- Backtests on 2019 Abqaiq, 2022 Russia diversion, and 2023-24 Red Sea Houthi attacks are bundled in `backend/backtests/` so reviewers can judge calibration on their own.
