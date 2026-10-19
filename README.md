# plant_floor_oee_febar

> One-line description of what this demo shows.

A Databricks demo project. Data lives in `nraameast1_catalog.plant_floor_oee_febar`; collateral is synced to the
workspace folder `/Workspace/Users/n.raam@databricks.com/plant_floor_oee_febar`.

## Quick start
```bash
# authenticate (SSO)
databricks auth login --host https://fevm-nraameast1.cloud.databricks.com --profile fevm-nraameast1

# warm resources + verify
ops/manage.sh start
ops/healthcheck.sh

# sync collateral to the workspace
ops/sync.sh
```

## Build order
1. `notebooks/` — create tables + volumes
2. `data_generation/` — generate synthetic data
3. `pipeline/` — build the medallion (bronze → silver → gold)
4. `agents/` — UC functions, Genie/Agent Bricks, governance
5. `app/` — deploy the Databricks App
6. `docs/` — demo script, runbook, deck, diagrams

## How to demo
See `docs/HOW_TO_DEMO_RUNBOOK.md`.
