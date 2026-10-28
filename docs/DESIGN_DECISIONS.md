# Design decisions and trade-offs

What was chosen at each stage, what it was weighed against, and what we gave up. Evidence for every claim:
[`EVIDENCE.md`](../EVIDENCE.md).

## 0 · Problem framing
- **Why OEE, and why "next shift".** Plant leadership already runs on OEE (availability × performance × quality), so
  value lands in a KPI they report. The shift is the unit a supervisor can act on: at handover they decide what runs,
  what gets maintenance, and what parts to stage. A daily or weekly prediction is too coarse to change that decision.
- **Why IT + OT together.** Neither side alone explains the loss. The historian shows vibration rising but not what it
  costs; ERP/MES shows the scrap and missed orders but not why. The 4 days before a breakdown run at 58.4 % OEE vs
  76.5 % otherwise, and only the joined data shows that both happen to the same asset at the same time.
- **Synthetic data, realistic defects.** We simulate one plant minute by minute, with failure ramps and the defects real
  feeds have (BAD OPC quality, sensor spikes, unmapped tags, negative scrap). The pipeline is judged on catching them.

## 1 · Lakeflow ingest
- **Declarative pipeline (SQL), not hand-written jobs.** Expectations, the event log, lineage and incremental refresh
  come built in; one SQL file per layer is reviewable by the plant's data team. Trade-off: less control over physical
  layout than a hand-tuned Spark job — fine at this volume (~2 M rows / 28 days / 12 assets).
- **Streaming tables for event feeds, materialized views for snapshots.** Historian, states, alarms, orders and work
  orders arrive as appended files → `STREAM read_files` (Auto Loader) processes only new files. Asset master, shift
  calendar and operators arrive as full snapshots → materialized views re-read them, so a renamed asset can't leave a
  stale row behind.
- **Expectation actions are chosen per rule.** Missing `asset_id` or a zero ideal cycle time **fails the update**: OEE
  would be wrong for the whole plant. A BAD-quality or out-of-range sensor reading is **dropped**: one bad minute
  shouldn't block a shift's OEE. Every drop is counted in the event log, and the counts match the injected defects.
- **The IT↔OT key map lives in the asset master** (`silver_assets.historian_prefix`), owned by IT, so every silver row
  resolves to one `asset_id`. The alternative, fuzzy matching tag names, breaks silently when controls renames a tag.
- **MES vs OT reconciliation is a gold output, not a filter.** A 257-unit (0.4 %) difference across 46 of 1,008 shifts is itself a
  finding (counter drift or unconfirmed production), so we report it instead of hiding it.

## 2 · Unity Catalog governance
- **IT, OT and integrated gold are tagged as separate domains** with owner and steward, because they really do have
  different owners (manufacturing IT vs controls engineering vs operations excellence). Gold OEE tables are `certified`,
  which is what Genie and the app are allowed to rely on.
- **Operator PII masked at the column**, in the pipeline DDL, so the mask is there from the first write and travels with
  the table into Genie and the app. Row filters were not needed: everyone in the plant may see every asset's OEE.
- **Limitation, stated plainly.** The demo workspace has no account-console access, so the HR group is a workspace group
  (`is_member`) and human-role grants are written as design only. In production they become account groups
  (`is_account_group_member`). Every real grant in this build goes to a service principal.

## 3 · ML and GenAI
- **Model: gradient-boosted trees on shift features**, label `next_shift_oee < 0.65`. Tabular, small data, mixed
  signals → boosted trees beat a deep model on effort and explainability. `class_weight="balanced"` because only ~12 %
  of shifts are at risk.
- **Time-based split, not random.** Train on the first 20 days, test on the last 8. A random split would leak a failure
  ramp into both sets and overstate accuracy.
- **Measured against what supervisors do today** ("this shift is already under 0.65"), not against zero. Precision
  0.82 vs 0.67 at recall 0.72 vs 0.65, i.e. fewer false alarms *and* more catches, plus 57–86 h of warning.
- **SHAP drivers per prediction** so the supervisor sees *why* (vibration trend, performance) and the LLM is grounded on
  the same reasons.
- **`ai_query` batch for root cause, not a chat call per click.** Root cause is needed only for at-risk assets, once per
  scoring run; batch keeps cost per shift predictable and the answer is stored in Delta, so it is governed and auditable.
  The prompt is grounded on past work orders for the same failure mode, and is told not to cite any reference it wasn't
  given (an earlier version invented SOP numbers).

## 4 · Lakebase
- **Why not have the app query Delta directly?** The supervisor screen needs millisecond point reads and *writes*
  (acknowledge, approve). A SQL warehouse is built for scans, not transactional updates. Lakebase gives Postgres
  semantics (0.024 ms point lookup) while UC stays the system of record.
- **Synced tables, two modes.** The at-risk queue is TRIGGERED (incremental, refreshed after each scoring run); shift OEE
  is a SNAPSHOT (rebuilt history). Lesson learned: never `CREATE OR REPLACE` a synced table's source, which changes the
  Delta table id and breaks the sync; publish with `MERGE`.
- **Writes go to a separate `ops` schema and are reverse-synced to Delta** (change data feed), so supervisor actions are
  analysable next to the predictions: that is how alert → first action (2.1 min) is measured.
- **Least privilege in Postgres too:** the app role can insert actions but may update only `status` and `updated_at`.

## 5 · Genie and agents
- **Genie for "what happened" questions,** over certified gold tables with example SQL, so OEE is always computed one way.
- **A Knowledge Assistant for "how do I fix it",** over the maintenance manuals and SOPs, with citations; Genie can't
  answer from documents.
- **An Agent Bricks Supervisor to combine them,** plus UC functions (`get_asset_risk`, `get_work_order_draft`) and the
  app's MCP tool. A single agent with one big prompt and SQL access would be harder to govern and test; each tool here
  has its own permissions and can be evaluated on its own.
- **The agent can propose a work order, never create one silently.** `request_work_order` pauses for human approval in
  the app. In a plant, an action that takes a machine out of production needs a named person.
- **Evaluated, not just demoed.** 10 questions with expected facts, scored by MLflow judges for correctness, relevance,
  safety, plant rules and routing. The first runs (correctness 0.7, plant rules 0.6) drove instruction fixes.

## 6 · Databricks App
- **App on Databricks, not a BI dashboard,** because the job is *act*, not just look: acknowledge, approve and ask, in
  one place, under the app's own service principal with only the resources it lists.
- **FastAPI + static UI** keeps the app small enough to read in one sitting.

## Platform choices
- **Serverless everywhere** (pipeline, jobs, warehouse, serving): no cluster management for a plant data team. Here it
  was also required, since the workspace is serverless-only.
- **Everything as code** (Asset Bundle for pipeline, jobs, Lakebase, app; Genie space and agents by script), so the
  whole build can be redeployed into the customer's workspace for a POC.

## What we'd do next in a POC
Replace synthetic feeds with the plant's historian and MES extracts through Lakeflow Connect or the existing landing zone;
swap assumptions A1–A6 in the value model for the customer's numbers; add account-group grants; and run the agent
eval on questions written by the plant's own supervisors.
