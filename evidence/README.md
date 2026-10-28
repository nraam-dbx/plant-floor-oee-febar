# Execution evidence

Text-readable proof that each stage ran: job-run outputs, live query results, model and agent output. Every file here
is under 9,000 characters so it is read in full. Job runs are rendered as Markdown with their outputs verbatim; the
complete exported notebooks (all code + outputs) are in [`raw/`](raw/). One-page summary: [`../EVIDENCE.md`](../EVIDENCE.md).

| File | Stage | What it proves | Regenerate |
|---|---|---|---|
| `01_generate_plant_data_run.md` | 1 · Lakeflow (source) | Generator job run: rows/files landed per IT/OT source, injected defects, ground-truth failure episodes | `python3 ops/export_run_evidence.py <task run id> evidence/raw/01_generate_plant_data_run.ipynb` then `ops/nb_to_md.py` |
| `02_lakeflow_pipeline.md` | 1 · Lakeflow | Pipeline update COMPLETED, row counts per layer, 18 expectations pass/fail from the event log, IT↔OT key resolution, OEE by work center, MES-vs-OT reconciliation | `python3 ops/stage1_evidence.py` |
| `02b_lakeflow_gold_reliability.md` | 1 · Lakeflow | MTTR / MTBF per asset, CNC-03 vibration rising for 4 days before its OEE drops, downtime linked to CMMS work orders, ML label balance | `python3 ops/stage1_evidence.py` |
| `03_unity_catalog.md` | 2 · Unity Catalog | Masked operator PII as seen by a non-HR user, registered column masks, mask function, IT / OT / gold domain + owner + steward + certification tags | `python3 ops/stage2_evidence.py` |
| `03b_unity_catalog_lineage.md` | 2 · Unity Catalog | Table lineage from `system.access.table_lineage`: raw volume → bronze → silver → gold → Lakebase and back | `python3 ops/stage2_evidence.py` |
| `04_train_oee_at_risk_run.md` | 3 · ML | Training job run: time split, model vs today's rule, confusion matrices, UC registration + `champion` alias + signature, warning hours before real failures, SHAP drivers. Warning hours are measured inside the test window only (CNC-03's first flag = test start, so its true lead is ≥ 86 h). | `ops/export_run_evidence.py` then `ops/nb_to_md.py` |
| `05_ml_genai.md` | 3 · ML + GenAI | UC model registry, `gold_asset_risk`, and for the at-risk asset the exact grounding passed to `ai_query` plus the parsed root cause / draft work order | `python3 ops/stage3_evidence.py` |
| `06_lakebase_setup_run.md` | 4 · Lakebase | Setup job run: OAuth connection to Postgres 17, `ops` DDL with REPLICA IDENTITY FULL, row counts, **grants held by the app's role**, at-risk queue read from Postgres, `EXPLAIN ANALYZE` point lookup (0.024 ms) | `databricks bundle run plant_oee_lakebase_setup` then export |
| `07_lakebase.md` | 4 · Lakebase | Forward synced tables online, reverse CDF streaming per `ops` table, replicated change feed in UC, alert→action KPI view | `python3 ops/stage4_evidence.py` |
| `08_genie_agents.md` | 5 · Genie + agents | Genie space config + a live question with the SQL Genie generated; Knowledge Assistant cited answer; Supervisor tools and a multi-tool answer | `python3 ops/stage5_evidence.py` |
| `09_agent_eval_run.md` | 5 · Agent eval | MLflow `genai.evaluate`, 10 plant questions: correctness 0.8, relevance 1.0, safety 1.0, plant_rules 1.0, routing 1.0, with judge rationale. Both correctness misses are judge errors (rounding "about 23 h" vs 22.95 h; penalising an extra, correct part LUB-FLT-10). Earlier runs, before instruction/rubric fixes: correctness 0.7, plant_rules 0.6. | `databricks bundle run plant_oee_agent_eval` then export |
| `10_app.md` | 6 · App | Least-privilege resources of the app's service principal, live API output from Lakebase, agent chat via the app, agent-raised work order → human approval, reverse-synced actions, alert→action 2.1 min | `python3 ops/stage6_evidence.py` |
