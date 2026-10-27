-- Stage 3b · GenAI root cause + draft work order for at-risk assets (ai_query on the SQL warehouse).
-- Endpoint: databricks-claude-sonnet-4-6 (newer Claude endpoints here reject batch inference via ai_query).
-- Grounding comes from the governed data, not the model's memory:
--   * this shift's OT signals and the model's top SHAP drivers  (gold_asset_risk)
--   * how the SAME failure mode was diagnosed and fixed before   (silver_work_orders, CMMS free text)
-- Output: gold_asset_risk_insights — one row per at-risk asset (risk >= model threshold). Healthy assets get no
-- narrative on purpose: an earlier version also explained the top-3 assets and the LLM invented faults for low-risk ones.

CREATE OR REPLACE TABLE nraameast1_catalog.plant_floor_oee_febar.gold_asset_risk_insights
COMMENT 'LLM root-cause hypothesis + draft CMMS work order per at-risk asset, grounded on OT signals, SHAP drivers and past work orders.'
AS
WITH ranked AS (
  SELECT r.*, a.asset_name, a.primary_failure_mode, a.criticality,
         row_number() OVER (ORDER BY r.risk_score DESC) AS risk_rank
  FROM nraameast1_catalog.plant_floor_oee_febar.gold_asset_risk r
  JOIN nraameast1_catalog.plant_floor_oee_febar.silver_assets a USING (asset_id)),
targets AS (SELECT * FROM ranked WHERE at_risk),
history AS (
  SELECT t.asset_id,
    array_join(slice(array_sort(collect_list(named_struct('ts', w.created_ts, 'txt',
      concat(w.asset_id, ' ', date_format(w.created_ts, 'yyyy-MM-dd'), ' [', w.failure_code, ', ',
             round((unix_timestamp(w.closed_ts) - unix_timestamp(w.actual_start_ts)) / 3600, 1), 'h]: ',
             w.problem_description, ' FIX: ', w.action_taken))),
      (l, r) -> CASE WHEN l.ts > r.ts THEN -1 WHEN l.ts < r.ts THEN 1 ELSE 0 END), 1, 6).txt, '\n') AS past_work_orders
  FROM targets t
  JOIN nraameast1_catalog.plant_floor_oee_febar.silver_work_orders w
    ON w.failure_code = t.primary_failure_mode AND w.wo_type = 'CORRECTIVE'
  GROUP BY t.asset_id),
prompts AS (
  SELECT t.*, coalesce(h.past_work_orders, 'none') AS past_work_orders,
    concat(
      'You are a reliability engineer at a turbine-component plant. Using ONLY the data below, explain the most likely ',
      'cause of the predicted next-shift OEE drop and draft a CMMS work order. Do not invent symptoms or readings that are ',
      'not in the data, and do not cite procedure numbers, manual sections or part numbers that are not given below; ',
      'if the evidence is weak, say so and lower confidence. Return ONLY a JSON object with keys: ',
      'probable_cause (string), evidence (array of short strings citing the numbers below), recommended_action (string), ',
      'urgency (one of: IMMEDIATE, NEXT_PLANNED_STOP, MONITOR), confidence (one of: high, medium, low), ',
      'work_order (object with priority P1|P2|P3, problem_description, planned_tasks array, estimated_hours number).\n\n',
      'ASSET: ', t.asset_id, ' (', t.asset_name, ', criticality ', t.criticality, ', typical failure mode ', t.primary_failure_mode, ')\n',
      'NEXT-SHIFT RISK of OEE < 0.65: ', round(t.risk_score, 3), ' (model v', t.model_version, ', scored on shift ', t.scored_shift_id, ')\n',
      'THIS SHIFT: OEE ', round(t.oee, 3), ', running vibration ', round(t.vib_mean_running, 2), ' mm/s (change vs prior 6 shifts ',
      round(t.vib_trend_vs_prev6, 2), '), max temperature ', round(t.temp_max, 1), ' C, vibration alarms ', t.vib_alarms, '\n',
      'TOP MODEL DRIVERS: ', array_join(t.top_drivers, '; '), '\n',
      'PAST CORRECTIVE WORK ORDERS FOR THIS FAILURE MODE (most recent first):\n', coalesce(h.past_work_orders, 'none')) AS prompt
  FROM targets t LEFT JOIN history h USING (asset_id)),
answered AS (
  SELECT *, ai_query('databricks-claude-sonnet-4-6', prompt, failOnError => false) AS resp FROM prompts)
SELECT asset_id, asset_name, scored_shift_id, risk_score, at_risk, top_drivers, past_work_orders,
  regexp_extract(resp.result, '(?s)\\{.*\\}', 0) AS insight_json,
  from_json(regexp_extract(resp.result, '(?s)\\{.*\\}', 0),
    'probable_cause STRING, evidence ARRAY<STRING>, recommended_action STRING, urgency STRING, confidence STRING,
     work_order STRUCT<priority: STRING, problem_description: STRING, planned_tasks: ARRAY<STRING>, estimated_hours: DOUBLE>') AS insight,
  resp.errorMessage AS llm_error,
  'databricks-claude-sonnet-4-6' AS llm_endpoint,
  current_timestamp() AS generated_at
FROM answered;

-- At-risk queue served to the app through Lakebase: every asset's latest risk, flattened (no arrays/structs)
-- so it maps cleanly to Postgres columns. Synced to Lakebase lb_at_risk_queue (resources/lakebase.yml, TRIGGERED).
-- Published with MERGE, never CREATE OR REPLACE: the synced table streams this table's change feed, and replacing the
-- table gave it a new Delta table id that broke the sync checkpoint (DIFFERENT_DELTA_TABLE_READ_BY_STREAMING_SOURCE).
CREATE TABLE IF NOT EXISTS nraameast1_catalog.plant_floor_oee_febar.gold_at_risk_queue
COMMENT 'One row per asset: latest next-shift risk + drivers + LLM work-order draft. Source of Lakebase lb_at_risk_queue.'
TBLPROPERTIES (delta.enableChangeDataFeed = true)
AS SELECT * FROM (SELECT r.asset_id, a.asset_name, a.work_center, a.criticality, r.scored_shift_id,
  round(r.oee, 4) AS current_oee, round(r.vib_mean_running, 3) AS vibration_mm_s, round(r.vib_trend_vs_prev6, 3) AS vibration_trend,
  round(r.risk_score, 4) AS risk_score, r.at_risk, array_join(r.top_drivers, '; ') AS top_drivers, r.model_version,
  i.insight.probable_cause, i.insight.recommended_action, i.insight.urgency, i.insight.confidence,
  i.insight.work_order.priority AS wo_priority, i.insight.work_order.problem_description AS wo_problem_description,
  array_join(i.insight.work_order.planned_tasks, '\n') AS wo_planned_tasks, i.insight.work_order.estimated_hours AS wo_estimated_hours,
  i.generated_at AS insight_generated_at, current_timestamp() AS published_at
FROM nraameast1_catalog.plant_floor_oee_febar.gold_asset_risk r
JOIN nraameast1_catalog.plant_floor_oee_febar.silver_assets a USING (asset_id)
LEFT JOIN nraameast1_catalog.plant_floor_oee_febar.gold_asset_risk_insights i USING (asset_id)) WHERE false;

MERGE INTO nraameast1_catalog.plant_floor_oee_febar.gold_at_risk_queue t
USING (SELECT r.asset_id, a.asset_name, a.work_center, a.criticality, r.scored_shift_id,
  round(r.oee, 4) AS current_oee, round(r.vib_mean_running, 3) AS vibration_mm_s, round(r.vib_trend_vs_prev6, 3) AS vibration_trend,
  round(r.risk_score, 4) AS risk_score, r.at_risk, array_join(r.top_drivers, '; ') AS top_drivers, r.model_version,
  i.insight.probable_cause, i.insight.recommended_action, i.insight.urgency, i.insight.confidence,
  i.insight.work_order.priority AS wo_priority, i.insight.work_order.problem_description AS wo_problem_description,
  array_join(i.insight.work_order.planned_tasks, '\n') AS wo_planned_tasks, i.insight.work_order.estimated_hours AS wo_estimated_hours,
  i.generated_at AS insight_generated_at, current_timestamp() AS published_at
FROM nraameast1_catalog.plant_floor_oee_febar.gold_asset_risk r
JOIN nraameast1_catalog.plant_floor_oee_febar.silver_assets a USING (asset_id)
LEFT JOIN nraameast1_catalog.plant_floor_oee_febar.gold_asset_risk_insights i USING (asset_id)) s
ON t.asset_id = s.asset_id
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *
WHEN NOT MATCHED BY SOURCE THEN DELETE;
