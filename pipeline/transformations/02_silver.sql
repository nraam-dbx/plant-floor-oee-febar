-- Silver: typed, validated, and keyed on ONE asset_id across IT and OT.
-- This is the IT/OT integration point: OT speaks historian tag paths (PLT1.WC_MACH.CNC03.VIBRATION),
-- IT speaks ERP equipment ids (EQ-10003); silver_assets carries both and every silver table resolves to asset_id.

-- ============ master data ============
CREATE OR REFRESH MATERIALIZED VIEW silver_assets (
  CONSTRAINT asset_id_present EXPECT (asset_id IS NOT NULL) ON VIOLATION FAIL UPDATE,
  CONSTRAINT valid_ideal_cycle EXPECT (ideal_cycle_time_s > 0) ON VIOLATION FAIL UPDATE
)
COMMENT 'Asset master: one row per asset with ERP id, historian prefix (IT<->OT key map), ideal cycle time.'
TBLPROPERTIES ('domain' = 'IT')
AS SELECT
  CAST(asset_id AS STRING) AS asset_id, CAST(erp_equipment_id AS STRING) AS erp_equipment_id,
  CAST(historian_prefix AS STRING) AS historian_prefix, asset_name, work_center, work_center_name,
  CAST(ideal_cycle_time_s AS INT) AS ideal_cycle_time_s, CAST(rated_power_kw AS DOUBLE) AS rated_power_kw,
  criticality, CAST(install_year AS INT) AS install_year, primary_failure_mode, plant
FROM bronze_it_assets;

CREATE OR REFRESH MATERIALIZED VIEW silver_shift_calendar
COMMENT 'Shift calendar: three 8-hour shifts per day (A 06-14, B 14-22, C 22-06).'
TBLPROPERTIES ('domain' = 'IT')
AS SELECT CAST(shift_id AS STRING) AS shift_id, CAST(shift_date AS DATE) AS shift_date, shift_code, crew,
  CAST(shift_start AS TIMESTAMP) AS shift_start, CAST(shift_end AS TIMESTAMP) AS shift_end,
  CAST(scheduled_minutes AS INT) AS scheduled_minutes
FROM bronze_it_shift_calendar;

CREATE OR REFRESH MATERIALIZED VIEW silver_operators
COMMENT 'Operator roster. full_name and badge_number are PII (masked in Unity Catalog).'
TBLPROPERTIES ('domain' = 'IT', 'contains_pii' = 'true')
AS SELECT CAST(operator_id AS STRING) AS operator_id, CAST(full_name AS STRING) AS full_name,
  CAST(badge_number AS STRING) AS badge_number, crew, certification_level
FROM bronze_it_operators;

-- ============ OT ============
CREATE OR REFRESH STREAMING TABLE silver_ot_historian (
  CONSTRAINT valid_timestamp   EXPECT (ts IS NOT NULL) ON VIOLATION DROP ROW,
  CONSTRAINT good_opc_quality  EXPECT (quality = 'GOOD' AND value IS NOT NULL) ON VIOLATION DROP ROW,
  CONSTRAINT physically_plausible EXPECT (
    CASE measure WHEN 'VIBRATION'   THEN value BETWEEN 0 AND 50
                 WHEN 'TEMPERATURE' THEN value BETWEEN -20 AND 200
                 WHEN 'POWER'       THEN value BETWEEN 0 AND 1000
                 ELSE value >= 0 END) ON VIOLATION DROP ROW,
  CONSTRAINT tag_mapped_to_asset EXPECT (asset_id IS NOT NULL) ON VIOLATION DROP ROW
)
COMMENT 'OT historian values resolved to asset_id + measure; bad-quality, impossible and unmapped readings dropped.'
TBLPROPERTIES ('domain' = 'OT')
AS SELECT a.asset_id, h.measure, h.ts, h.value, h.quality, h.tag_name
FROM (
  SELECT tag_name,
         regexp_extract(tag_name, '^(.*)\\.[A-Z_]+$', 1) AS historian_prefix,
         element_at(split(tag_name, '\\.'), -1)          AS measure,
         CAST(ts AS TIMESTAMP) AS ts, CAST(value AS DOUBLE) AS value, quality
  FROM STREAM(bronze_ot_historian)
) h
LEFT JOIN silver_assets a ON h.historian_prefix = a.historian_prefix;

CREATE OR REFRESH MATERIALIZED VIEW silver_ot_tag_minute
COMMENT 'One row per asset per minute with each measure as a column (dedupes store-and-forward repeats).'
TBLPROPERTIES ('domain' = 'OT')
AS SELECT asset_id, ts,
  avg(CASE WHEN measure = 'VIBRATION'   THEN value END) AS vibration_mm_s,
  avg(CASE WHEN measure = 'TEMPERATURE' THEN value END) AS temperature_c,
  avg(CASE WHEN measure = 'POWER'       THEN value END) AS power_kw,
  max(CASE WHEN measure = 'CYCLE_COUNT' THEN value END) AS cycle_count
FROM silver_ot_historian
GROUP BY asset_id, ts;

CREATE OR REFRESH STREAMING TABLE silver_ot_machine_states (
  CONSTRAINT valid_interval EXPECT (end_ts > start_ts) ON VIOLATION DROP ROW,
  CONSTRAINT known_state EXPECT (state IN ('RUNNING', 'IDLE', 'SETUP', 'PLANNED_DOWN', 'UNPLANNED_DOWN')) ON VIOLATION DROP ROW,
  CONSTRAINT equipment_mapped EXPECT (asset_id IS NOT NULL) ON VIOLATION DROP ROW
)
COMMENT 'SCADA machine-state intervals resolved to asset_id.'
TBLPROPERTIES ('domain' = 'OT')
AS SELECT a.asset_id, s.state, s.reason_code,
  CAST(s.start_ts AS TIMESTAMP) AS start_ts, CAST(s.end_ts AS TIMESTAMP) AS end_ts,
  timestampdiff(SECOND, CAST(s.start_ts AS TIMESTAMP), CAST(s.end_ts AS TIMESTAMP)) / 60.0 AS duration_min
FROM STREAM(bronze_ot_machine_states) s
LEFT JOIN silver_assets a ON s.equipment_path = a.historian_prefix;

CREATE OR REFRESH STREAMING TABLE silver_ot_alarms (
  CONSTRAINT equipment_mapped EXPECT (asset_id IS NOT NULL) ON VIOLATION DROP ROW
)
COMMENT 'SCADA alarms resolved to asset_id.'
TBLPROPERTIES ('domain' = 'OT')
AS SELECT a.asset_id, l.alarm_code, l.severity, CAST(l.alarm_ts AS TIMESTAMP) AS alarm_ts, l.value, l.message
FROM STREAM(bronze_ot_alarms) l
LEFT JOIN silver_assets a ON l.equipment_path = a.historian_prefix;

-- ============ IT ============
CREATE OR REFRESH STREAMING TABLE silver_production_orders (
  CONSTRAINT equipment_mapped EXPECT (asset_id IS NOT NULL) ON VIOLATION DROP ROW,
  CONSTRAINT positive_plan EXPECT (planned_qty > 0) ON VIOLATION DROP ROW
)
COMMENT 'ERP/MES production orders resolved from ERP equipment id to asset_id.'
TBLPROPERTIES ('domain' = 'IT')
AS SELECT CAST(o.order_id AS STRING) AS order_id, a.asset_id, o.erp_equipment_id, CAST(o.shift_id AS STRING) AS shift_id,
  o.part_number, CAST(o.planned_qty AS INT) AS planned_qty,
  CAST(o.scheduled_start AS TIMESTAMP) AS scheduled_start, CAST(o.scheduled_end AS TIMESTAMP) AS scheduled_end,
  CAST(o.operator_id AS STRING) AS operator_id
FROM STREAM(bronze_it_production_orders) o
LEFT JOIN silver_assets a ON o.erp_equipment_id = a.erp_equipment_id;

CREATE OR REFRESH STREAMING TABLE silver_production_confirmations (
  CONSTRAINT non_negative_yield EXPECT (yield_qty >= 0) ON VIOLATION DROP ROW,
  CONSTRAINT non_negative_scrap EXPECT (scrap_qty >= 0) ON VIOLATION DROP ROW,
  CONSTRAINT equipment_mapped EXPECT (asset_id IS NOT NULL) ON VIOLATION DROP ROW
)
COMMENT 'MES confirmations: good (yield) and scrap quantity per production order.'
TBLPROPERTIES ('domain' = 'IT')
AS SELECT CAST(c.confirmation_id AS STRING) AS confirmation_id, CAST(c.order_id AS STRING) AS order_id, a.asset_id,
  CAST(c.confirmed_ts AS TIMESTAMP) AS confirmed_ts, c.yield_qty, c.scrap_qty,
  c.yield_qty + c.scrap_qty AS total_qty, c.scrap_reason
FROM STREAM(bronze_it_production_confirmations) c
LEFT JOIN silver_assets a ON c.erp_equipment_id = a.erp_equipment_id;

CREATE OR REFRESH STREAMING TABLE silver_work_orders (
  CONSTRAINT equipment_mapped EXPECT (asset_id IS NOT NULL) ON VIOLATION DROP ROW,
  CONSTRAINT closed_after_created EXPECT (closed_ts IS NULL OR closed_ts >= created_ts) ON VIOLATION DROP ROW
)
COMMENT 'CMMS work orders resolved to asset_id; problem_description / action_taken are free text for GenAI.'
TBLPROPERTIES ('domain' = 'IT')
AS SELECT CAST(w.wo_id AS STRING) AS wo_id, a.asset_id, w.erp_equipment_id, w.wo_type, w.priority, w.failure_code,
  w.problem_description, w.action_taken,
  CAST(w.created_ts AS TIMESTAMP) AS created_ts, CAST(w.actual_start_ts AS TIMESTAMP) AS actual_start_ts,
  CAST(w.closed_ts AS TIMESTAMP) AS closed_ts, CAST(w.technician_id AS STRING) AS technician_id,
  CAST(w.labor_hours AS DOUBLE) AS labor_hours
FROM STREAM(bronze_it_work_orders) w
LEFT JOIN silver_assets a ON w.erp_equipment_id = a.erp_equipment_id;
