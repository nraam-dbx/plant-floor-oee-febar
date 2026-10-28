# Value model — plant-floor OEE (IT/OT integration)

Every number is either **measured** in the demo (synthetic data, 12 assets, 28 days, query in `evidence/`) or an
**assumption** (labelled A1…A6, to be replaced with the customer's figures in the POC). Scope: one 12-asset production line.

## Measured baseline (28 days)
| Metric | Value | Source |
|---|---|---|
| Plant OEE | 74.1 % (target 75 %) | `evidence/12` |
| Asset-shifts inside a degrade → fail window (4 days before a major failure) | 130 of 1,008 (13 %) | `evidence/12` (`gold_oee_shift` × `gold_downtime_events`) |
| OEE in those shifts vs all other shifts | **58.5 % vs 76.4 %** | `evidence/12` |
| Scrap rate in those shifts vs others | 7.0 % vs 1.9 % → ≈ 452 excess parts | `evidence/12` |
| Major (run-to-failure) stops | 10, avg 5.3 h, 53.2 h total | `evidence/12` |
| Model on held-out 8 days | precision 0.82, recall 0.72 (today's rule: 0.67 / 0.65) | `evidence/04` |
| Warning lead time before real failures | 57 – 86 h | `evidence/04` |
| Alert → first supervisor action | 2.1 min (app) | `gold_alert_response`, `evidence/10` |

## Assumptions
| ID | Assumption | Base | Range |
|---|---|---|---|
| A1 | Share of a degradation window's loss recovered by intervening at the first flag (flags arrive 2–3 days before failure, mid-ramp) | 60 % | 60 – 100 % |
| A2 | Detection rate in production = test recall | 72 % | 50 – 72 % |
| A3 | Cost of one unplanned hour on a constrained cell (lost contribution + overtime + expedite) | $5,000 | $2,500 – $10,000 |
| A4 | A planned intervention hour costs this share of an unplanned hour | 30 % | — |
| A5 | Cost of one scrapped in-process part (superalloy blade / vane segment at machining or coating stage) | $400 | $200 – $1,000 |
| A6 | Annualization factor 365 / 28 | 13.0 | — |

## Annual effect per 12-asset line
| Lever | Formula | Low | Base | High |
|---|---|---|---|---|
| OEE points | 2.3 pts gap (76.4 − 74.1) × A2 × A1 | +0.7 | **+1.0** | +1.7 (theoretical max +2.3 if every window is caught) |
| Unplanned hours avoided | 53.2 h × A6 × A2 | 350 h | **500 h** | 500 h |
| Downtime value | hours × A3 × (1 − A4) | $0.6 M | **$1.75 M** | $3.5 M |
| Scrap avoided | 452 × A6 × A2 × A1 | 1,800 parts | **2,500 parts** | 4,200 parts |
| Scrap value | parts × A5 | $0.35 M | **$1.0 M** | $4.2 M |
| **Total** | | **≈ $1.0 M** | **≈ $2.75 M** | **≈ $7.7 M** |

Not counted (upside): secondary damage avoided by not running to failure, throughput gained in recovered shifts (would
double-count downtime), MTTR reduction from pre-staged parts and AI-drafted work orders (not measured in the demo).
Platform run cost (serverless pipeline/jobs, Lakebase 0.5–2 CU, model + agent serving) to be sized in the POC.
