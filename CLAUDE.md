# plant_floor_oee_febar — Project Notes

## Environment
| | |
|---|---|
| Workspace | https://fevm-nraameast1.cloud.databricks.com |
| Catalog / schema | `nraameast1_catalog.plant_floor_oee_febar` |
| SQL warehouse | `ba24ff79986686a9` |
| CLI profile | `fevm-nraameast1` |
| App | `plant-floor-oee-febar` |
| Workspace folder | `/Workspace/Users/n.raam@databricks.com/plant_floor_oee_febar` |

All settings live in `config.env` (single source of truth); `ops/*.sh` source it.

## Conventions
- Catalog/schema/table names use **underscores** only (never hyphens).
- Medallion layers are **table-name prefixes** (`bronze_*`/`silver_*`/`gold_*`) in one schema.
- All collateral lives in the workspace folder above — run `ops/sync.sh` after edits.
- Run `ops/*.sh` **from the project root** (paths are relative; scripts resolve their own dir).

## Structure
- `notebooks/`       — DDL (create tables, volumes)
- `data_generation/` — synthetic data scripts
- `pipeline/`        — medallion transforms + any streaming
- `agents/`          — UC functions, agent/Genie setup, governance SQL
- `app/`             — Databricks App (server/ + client/ + app.yaml)
- `ops/`             — manage.sh, healthcheck.sh, sync.sh
- `docs/`            — demo script, runbook, diagrams, deck builder

## Deploy (app)
```
cd app
databricks sync . /Workspace/Users/n.raam@databricks.com/plant_floor_oee_febar/app -p fevm-nraameast1 --exclude .venv --exclude __pycache__ --exclude .git --exclude '*.pyc'
databricks apps deploy plant-floor-oee-febar --source-code-path /Workspace/Users/n.raam@databricks.com/plant_floor_oee_febar/app -p fevm-nraameast1
```

## Notes / issues encountered
<!-- Log fixes and conventions here as the project evolves. -->

## FEBAR submission
- Purpose: FEBAR exam build AND a real customer need (power-generation equipment manufacturer — IT/OT integration to raise plant-floor OEE).
- Six integrated stages: Lakeflow → UC → Lakebase → ML/GenAI → Genie → App, all keyed on `asset_id` / `work_center`.
- IT data (ERP/MES: production orders, work orders, quality/scrap, shifts) + OT data (historian/SCADA tag time-series, machine states/alarms).
  OEE = Availability × Performance × Quality. KPIs: OEE %, unplanned downtime hrs, MTTR/MTBF, scrap rate, throughput.
- GitHub: https://github.com/nraam-dbx/plant-floor-oee-febar (PRIVATE while building; make PUBLIC before submitting).
  Local git pinned to `nraam-dbx` via repo-local credential.helper (global active gh account is `n-raam_data`).
  `gh` for this repo: prefix with `GH_TOKEN=$(gh auth token --user nraam-dbx)`.
- **Confidentiality:** the repo is public-bound. NO customer name, people, or customer data in tracked files — say
  "a power-generation equipment manufacturer". Synthetic data only. Customer-named collateral goes in
  `customer_private/` (gitignored, never pushed).
- Evidence rule: evaluator reads TEXT only. Commit outputs to `evidence/` (ipynb with outputs, JSON/CSV, logs).

## Design (six stages, one data journey)
1. **Lakeflow** — OT: 1-min historian tags + machine states/alarms (Auto Loader, streaming) · IT: ERP/MES production
   orders, work orders, scrap/rework, shift calendar (batch). SDP pipeline w/ expectations → bronze/silver/gold;
   `gold_oee_shift` = Availability × Performance × Quality per asset per shift.
2. **Unity Catalog** — IT vs OT domains, owner/steward tags, lineage tag→OEE, operator-ID masking.
3. **ML/GenAI** — MLflow model (UC, with signature) predicting next-shift OEE < target; `ai_query` + manuals
   Vector Search for probable root cause and draft work order.
4. **Lakebase** — synced at-risk table for low-latency app reads; supervisor actions written to Postgres and
   reverse-synced to Delta (alert→action latency).
5. **Genie agent** — two layers:
   - Genie space "Plant OEE Analyst" over gold OEE, downtime reasons, risk scores, work orders (instructions,
     sample SQL, trusted assets), with Agent mode for multi-step "why did OEE drop?" analysis.
   - Agent Bricks **Supervisor** "Plant-Floor OEE Agent" routing to: the Genie space (metrics), a Knowledge
     Assistant over repair manuals/SOPs (how to fix), and UC function tools (`get_asset_risk`,
     `create_work_order` → Lakebase). Served endpoint; evaluated with MLflow LLM judges.
6. **App** — OEE board + at-risk queue (Lakebase) + chat panel calling the Supervisor agent.
