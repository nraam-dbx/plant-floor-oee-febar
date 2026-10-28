# Plant-floor OEE: IT + OT on one Databricks platform

**Problem.** A power-generation equipment manufacturer's component plants keep machine data (historian / SCADA, the
OT side) and business data (ERP / MES / CMMS, the IT side) in separate systems with different asset identifiers.
Nobody can see, early enough, that a machine is degrading, so slow failures run all the way to breakdowns. In this demo
the 4 days before a breakdown run at **58.5 % OEE vs 76.4 %** otherwise, with 3.7× the scrap rate ([`evidence/12`](evidence/12_value_baseline.md)).

**What this builds.** One end-to-end data journey on Databricks, from raw synthetic plant data to a supervisor taking
action, keyed on a single `asset_id`:

| # | Stage | Databricks | Here |
|---|---|---|---|
| 1 | Ingest | Lakeflow declarative pipeline, Auto Loader | Historian tags, SCADA states/alarms, ERP/MES orders + confirmations, CMMS work orders → bronze / silver / gold with 18 data-quality expectations |
| 2 | Govern | Unity Catalog | IT / OT / gold domain tags with owner + steward, certified gold, operator PII masks, lineage |
| 3 | Predict + explain | MLflow model in UC, `ai_query` | Next-shift OEE-at-risk model (signature, `champion` alias, SHAP drivers); LLM root cause + work-order draft grounded on past repairs |
| 4 | Serve + act | Lakebase (Postgres) | Synced at-risk queue + shift OEE for the app; supervisor actions written to Postgres and reverse-synced to Delta |
| 5 | Ask | Genie, Agent Bricks Supervisor + Knowledge Assistant | "Plant OEE Analyst" Genie space, manuals Knowledge Assistant, UC function tools, app MCP tool; MLflow LLM-judge eval |
| 6 | Use | Databricks App | OEE board, at-risk queue with actions, work-order approvals, agent chat with human approval for agent actions |

**Results (synthetic data, 12 assets, 28 days).** The model beats today's rule (precision 0.82 vs 0.67, recall 0.72 vs
0.65, AUC 0.87) and flagged the held-out breakdowns 57–86 h ahead. The agent routes to the right tool 10/10.
Alert → first supervisor action: 2.1 min. Value per 12-asset line, base case: +1.0 OEE point, ~500 fewer unplanned
hours, ≈ $2.75 M / year (range $1.0 M – $7.7 M; assumptions in [`docs/deck/VALUE_MODEL.md`](docs/deck/VALUE_MODEL.md)).

* **Start here:** [`EVIDENCE.md`](EVIDENCE.md) (what ran, with the real output per stage) · [`docs/DESIGN_DECISIONS.md`](docs/DESIGN_DECISIONS.md) (choices and trade-offs)
* **Business deck:** [`docs/FEBAR_business_deck.pdf`](docs/FEBAR_business_deck.pdf)
* **Execution evidence (text):** [`evidence/`](evidence/README.md): job-run outputs, live query results, eval scores (each file < 9,000 chars; full notebook exports in `evidence/raw/`)
* **Demo:** [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md) · runbook [`docs/HOW_TO_DEMO_RUNBOOK.md`](docs/HOW_TO_DEMO_RUNBOOK.md)

All data is synthetic (`data_generation/generate_plant_data.py`, seed 42). No customer data, names or systems appear
in this repository.

## Repository map
| Path | What |
|---|---|
| `databricks.yml`, `resources/` | Databricks Asset Bundle: pipeline, jobs, Lakebase project + synced tables, app with its least-privilege resources |
| `data_generation/` | Minute-level plant simulator → raw IT/OT extracts in a UC volume |
| `pipeline/transformations/` | Lakeflow SQL: `01_bronze`, `02_silver` (IT↔OT key resolution, expectations, masks), `03_gold` (OEE, downtime, reliability, ML features) |
| `notebooks/` | `00_setup.sql`, `10_train_oee_at_risk.py` (model), `11_genai_root_cause.sql` (`ai_query`), `20_eval_supervisor.py` (LLM judges) |
| `lakebase/` | Postgres `ops` DDL, app grants, reverse-sync views, synced-table refresh |
| `agents/` | Governance SQL, UC function tools, Genie space as code, manuals, Supervisor instructions + Agent Bricks setup |
| `app/` | FastAPI app + static UI + MCP server (`request_work_order`) |
| `ops/` | Build/evidence helpers, health check, post-deploy grants |
| `evidence/` | Text evidence per stage (see its README) |

## Rebuild from scratch
```bash
databricks auth login --host https://<workspace> --profile fevm-nraameast1     # values in config.env
python3 ops/run_sql_file.py notebooks/00_setup.sql                            # schema + raw volume
python3 ops/run_sql_file.py agents/01_governance.sql                          # mask function (+ tags after first build)
databricks bundle deploy
databricks bundle run plant_oee_build             # generate → pipeline → train → GenAI → Lakebase sync
databricks bundle run plant_oee_lakebase_setup    # ops tables in Postgres
./ops/lakebase_reverse_sync.sh                    # CDF reverse sync (once)
python3 ops/run_sql_file.py agents/02_uc_functions.sql && python3 agents/03_genie_space.py
./agents/05_agent_bricks_setup.sh                 # Knowledge Assistant + Supervisor + tools
databricks bundle run plant_floor_oee_app && ./ops/app_post_deploy.sh
databricks bundle run plant_oee_agent_eval
```
The workspace used is serverless-only; every job runs on serverless compute.
