-- Stage 5 · UC function tools for the Plant-Floor OEE Supervisor agent. Comments are the tool descriptions the
-- supervisor reads, so they say exactly when to use each tool. Run: python3 ops/run_sql_file.py agents/02_uc_functions.sql

USE CATALOG nraameast1_catalog;
USE SCHEMA plant_floor_oee_febar;

CREATE OR REPLACE FUNCTION get_asset_risk(
  asset_filter STRING DEFAULT NULL COMMENT 'Asset id such as CNC-02, or NULL for every asset'
)
RETURNS TABLE (asset_id STRING, asset_name STRING, work_center STRING, criticality STRING, scored_shift_id STRING,
               current_oee DOUBLE, vibration_mm_s DOUBLE, vibration_trend DOUBLE, risk_score DOUBLE, at_risk BOOLEAN,
               top_drivers STRING, urgency STRING)
COMMENT 'Predicted risk that an asset''s NEXT-shift OEE falls below the 65% floor (ML model oee_at_risk_model@champion), with the top model drivers. Use for "which assets are at risk", "what is the risk for CNC-02", "why is X flagged". Sorted highest risk first.'
RETURN
  SELECT asset_id, asset_name, work_center, criticality, scored_shift_id, current_oee, vibration_mm_s, vibration_trend,
         risk_score, at_risk, top_drivers, urgency
  FROM nraameast1_catalog.plant_floor_oee_febar.gold_at_risk_queue
  WHERE asset_filter IS NULL OR upper(asset_id) = upper(asset_filter)
  ORDER BY risk_score DESC;

CREATE OR REPLACE FUNCTION get_work_order_draft(
  asset_filter STRING COMMENT 'Asset id such as CNC-02'
)
RETURNS TABLE (asset_id STRING, risk_score DOUBLE, probable_cause STRING, recommended_action STRING, urgency STRING,
               confidence STRING, wo_priority STRING, wo_problem_description STRING, wo_planned_tasks STRING,
               wo_estimated_hours DOUBLE, insight_generated_at TIMESTAMP)
COMMENT 'The AI-drafted root cause and CMMS work order for an AT-RISK asset (grounded on OT signals, model drivers and past work orders). Use when asked what is likely wrong with an at-risk asset or to prepare/draft a work order. Returns no draft fields for assets that are not at risk. The draft must be confirmed by a person in the plant-floor app before it is created.'
RETURN
  SELECT asset_id, risk_score, probable_cause, recommended_action, urgency, confidence, wo_priority,
         wo_problem_description, wo_planned_tasks, wo_estimated_hours, insight_generated_at
  FROM nraameast1_catalog.plant_floor_oee_febar.gold_at_risk_queue
  WHERE upper(asset_id) = upper(asset_filter);
