# Evidence summary — what actually ran

All numbers below are copied from committed run output (synthetic data, 12 assets, 5 work centers, 28 days, seed 42;
workspace build of 2026-10-27). Each row links to the file with the full output. Index: [`evidence/README.md`](evidence/README.md).

One asset, end to end: **CNC-02**. Its OT vibration trend rises → the pipeline joins it to IT orders and quality →
the model scores it 0.998 at risk → `ai_query` drafts the root cause from past repairs → Lakebase serves it to the app →
the Supervisor agent answers "what do I do?" with the procedure and parts → a supervisor approves the agent's work
order in the app → the action is reverse-synced to Delta and measured (alert → first action 2.1 min).

| # | Stage | Result (verbatim from output) | File |
|---|---|---|---|
| 1 | Source data | 1,939,980 historian rows, 8,730 machine states, 786 alarms, 1,367 production orders + confirmations, 147 CMMS work orders landed in a UC volume; injected defects: 2,818 BAD-quality, 673 spikes, 3 negative-scrap, 2,688 unmapped tag rows | [`01`](evidence/01_generate_plant_data_run.md) |
| 1 | Lakeflow | Pipeline update `COMPLETED` (full refresh, job task). 15 tables bronze → silver → gold (`gold_oee_shift` 1,008 asset-shifts). 18 expectations from the event log; the injected defects are exactly what was dropped: `good_opc_quality` 2,818 failed, `tag_mapped_to_asset` 2,688, `non_negative_scrap` 3. Every silver row resolves to one `asset_id` across ERP key `EQ-1000x` and historian prefix `PLT1.WC_*`. MES vs OT unit counts: 72,296 vs 72,457 | [`02`](evidence/02_lakeflow_pipeline.md) |
| 1 | Gold | Lowest OEE: Root Form Grinding 71.4 %. MTTR 28.6 – 108.9 min, MTBF 19.2 – 63.3 h per asset. CNC-03 vibration climbs 2.2 → 7.8 mm/s over 4 days while OEE falls 0.78 → 0.46, then a 327-min spindle failure | [`02b`](evidence/02b_lakeflow_gold_reliability.md) |
| 2 | Unity Catalog | Non-HR user sees `A***` / `B***` for operator name and badge (column masks on bronze + silver, `is_member('plant_hr_admins')`). 30 tables tagged IT / OT / IT_OT with owner + steward; gold `certified`. Lineage from the raw volume to the Lakebase synced tables and back | [`03`](evidence/03_unity_catalog.md), [`03b`](evidence/03b_unity_catalog_lineage.md) |
| 3 | ML | Next-shift OEE-at-risk model, time split (train 720 / test 276 shifts). Precision 0.816 vs 0.667 for today's rule, recall 0.721 vs 0.651, AUC 0.869. Flagged the 3 test-window failures 57 – 86 h ahead. Registered in UC with signature, alias `champion` → v4 | [`04`](evidence/04_train_oee_at_risk_run.md) |
| 3 | GenAI | `ai_query` (`databricks-claude-sonnet-4-6`) grounded on the 4 past spindle-bearing work orders → CNC-02: "spindle bearing wear, most likely driven by lubrication starvation", urgency IMMEDIATE, with cited evidence from the shift's signals | [`05`](evidence/05_ml_genai.md) |
| 4 | Lakebase | Postgres 17 project; `gold_at_risk_queue` → `lb_at_risk_queue` (TRIGGERED) and `gold_oee_shift` → `lb_oee_shift` (SNAPSHOT) online. App role holds SELECT on synced tables, SELECT+INSERT on `ops.*`, UPDATE on 2 columns only. Point lookup 0.024 ms. Reverse sync `CDF_STATE_STREAMING` for both `ops` tables | [`06`](evidence/06_lakebase_setup_run.md), [`07`](evidence/07_lakebase.md) |
| 5 | Genie | "Plant OEE Analyst" space (7 tables, 5 example SQLs). Asked "lowest OEE work center and biggest loss?" → generated SQL over `gold_oee_shift` → "WC_GRND 71.41 %, biggest loss performance 0.8147" | [`08`](evidence/08_genie_agents.md) |
| 5 | Agents | Knowledge Assistant over manuals: part SP-BRG-7014-P4, procedure MM-CNC-01-R7. Supervisor routes `get_asset_risk → get_work_order_draft → plant_maintenance_manuals` for "what should I do about CNC-02?" | [`08`](evidence/08_genie_agents.md) |
| 5 | Eval | MLflow `genai.evaluate`, 10 questions with expected facts: routing 1.0, relevance 1.0, safety 1.0, plant_rules 1.0, correctness 0.8 (both misses are judge errors, rationale in file). Before instruction fixes: 0.7 / 0.6 | [`09`](evidence/09_agent_eval_run.md) |
| 6 | App | Service principal gets only the resources it uses (Lakebase, 2 endpoints, Genie, warehouse, 2 functions, 7 tables). `GET /api/summary` → plant OEE 73.7 %, 39.5 unplanned h, 1 at risk. Agent raised a P1 work order through the app's MCP tool, paused for approval, approved by a person (`REQUESTED → APPROVED` in the change feed) | [`10`](evidence/10_app.md) |
| — | Value baseline | Shifts from 4 days before a major failure until the machine is back: 133 of 1,008 (13.2 %), OEE 58.4 % vs 76.5 %, scrap 6.9 % vs 1.9 % (452 excess parts), 63 vs 77 unplanned h; 10 major stops, 53.2 h. Inputs to [`VALUE_MODEL.md`](docs/deck/VALUE_MODEL.md) | [`12`](evidence/12_value_baseline.md) |

Design choices and trade-offs: [`docs/DESIGN_DECISIONS.md`](docs/DESIGN_DECISIONS.md).
