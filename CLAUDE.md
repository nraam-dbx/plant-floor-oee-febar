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

## Build (Stage 1 — data + Lakeflow), Databricks Asset Bundle at repo root
```
# one-time: schema + raw volume (notebooks/00_setup.sql, run on the warehouse)
databricks bundle deploy                 # target dev, profile fevm-nraameast1
databricks bundle run plant_oee_build    # generate_data (serverless nb) -> plant_oee_medallion (full refresh)
```
- Generator: `data_generation/generate_plant_data.py` → `/Volumes/nraameast1_catalog/plant_floor_oee_febar/raw/{ot,it}/…`
  (28 days from 2026-09-21, seed 42, 12 assets / 5 work centers). OT keyed by historian tag path, IT by ERP `EQ-1000x`;
  `silver_assets.historian_prefix` is the IT↔OT key map.
- Pipeline SQL: `pipeline/transformations/01_bronze|02_silver|03_gold.sql`; `${raw_path}` from pipeline config.

## Governance (Stage 2)
`python3 ops/run_sql_file.py agents/01_governance.sql` (mask function + tags) → evidence `python3 ops/stage2_evidence.py`.

## ML + GenAI (Stage 3)
- `notebooks/10_train_oee_at_risk.py` (job task `train_at_risk_model`, serverless): HistGradientBoosting on `gold_shift_features`,
  label `next_shift_oee < 0.65`, time split 20d/8d, registers `oee_at_risk_model` (alias `champion`), writes `gold_asset_risk` + SHAP drivers.
- `notebooks/11_genai_root_cause.sql` (SQL task `genai_root_cause`): `ai_query` → `gold_asset_risk_insights` for at-risk assets only.
- Rerun just these: `databricks bundle run plant_oee_build --only train_at_risk_model,genai_root_cause`. Evidence: `python3 ops/stage3_evidence.py`.

## Lakebase (Stage 4)
- Project `projects/plant-floor-oee-febar` (PG17, 0.5–2 CU, suspend 300s) + synced tables in `resources/lakebase.yml`:
  `gold_at_risk_queue → lb_at_risk_queue` (TRIGGERED, pk asset_id), `gold_oee_shift → lb_oee_shift` (SNAPSHOT). In Postgres:
  db `databricks_postgres`, schema `plant_floor_oee_febar`. Build job task `refresh_lakebase_sync` triggers both after each build.
- Writable tables `ops.supervisor_actions`, `ops.work_order_requests` (`lakebase/01_ops_schema.sql`, job `plant_oee_lakebase_setup`).
- Reverse sync: CDF config `ops_to_uc` (`ops/lakebase_reverse_sync.sh`, run once) → UC `lb_supervisor_actions_history`,
  `lb_work_order_requests_history`; views `gold_supervisor_actions`, `gold_work_order_requests`, `gold_alert_response`
  (`lakebase/02_reverse_sync_views.sql`). Smoke-test rows use `acted_by='setup-smoke-test'` and are excluded from KPIs.
- Evidence: `python3 ops/stage4_evidence.py`.

## Notes / issues encountered
- Do NOT reuse anything from the volta projects (user instruction). Build Lakebase sync etc. fresh.
- **Workspace is SERVERLESS-ONLY** ("Only serverless compute is supported"): no job/ML clusters. ML notebook pip-installs
  mlflow/sklearn/shap. Always read full `bundle deploy` output — a failed deploy once left the job on old tasks.
- Workspace has many workspace-wide **governed tag policies** (`Domain`, `PII`, `data_owner`, `data_product`…). Our UC tags
  are prefixed `oee_` (`oee_domain`, `oee_layer`, `oee_data_owner`, `oee_data_steward`, `oee_pii`); gold uses the governed
  `system.certification_status = certified`; schema uses `data_product = analytics` (allowed value).
- PII masks live in the pipeline SQL (`MASK ${uc_catalog}.${uc_schema}.mask_pii`) — `mask_pii` must exist before the
  pipeline runs (agents/01_governance.sql). Tags set by ALTER survive pipeline updates.
- `ai_query` endpoint: `databricks-claude-sonnet-4-6`. sonnet-5-5 errors "not supported for batch inference"; sonnet-5 / gpt-5-4
  also failed a 1-row ai_query test. LLM invented SOP/manual refs until the prompt forbade un-given references.
- MLflow pyfunc of an sklearn model logged with `pyfunc_predict_fn="predict_proba"` returns [n,2] — take column 1.
- No CREATE CATALOG on the metastore → no Lakebase UC catalog; synced tables sit in the project schema (`branch` + `postgres_database` set).
- CDF reverse sync silently SKIPS tables without `REPLICA IDENTITY FULL` (see `list-cdf-statuses <cdf-config>`).
- psycopg-binary on serverless aborts the Python process (SIGABRT) during libpq's GSSAPI probe → always `gssencmode="disable"`.
  The job still reported SUCCESS after the crash → notebooks end with an assert + `dbutils.notebook.exit`.
- `databricks jobs run-now --json` needs `job_id` inside the JSON (positional arg + --json errors); don't discard its output.
- PyPI is blocked on this laptop → anything needing pip runs as a Databricks task.
- Statements API is stateless: `ops/run_sql_file.py` turns `USE CATALOG/SCHEMA` into request catalog/schema params.
- `plant_hr_admins` is a WORKSPACE group (id 2126379324037637); mask uses `is_member()` because there is no account-console access
  on the FEVM account, so `is_account_group_member()` can't see it. Unmask path (adding a member) not yet verified.
- Not an account admin on the FEVM account (profile `fevm-account` saved, account APIs return 'disabled for users without
  account admin'). UC grants need account groups → human-role grants are DESIGN-only in agents/01_governance.sql.
  Real grants go to service principals (App, agents) in their stages. Don't grant to `account users`.
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
