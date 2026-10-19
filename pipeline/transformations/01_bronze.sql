-- Bronze: raw IT + OT extracts landed by the source systems, ingested incrementally with Auto Loader.
-- Kept as strings/as-landed; typing, key mapping and quality rules happen in silver.
-- ${raw_path} is set in the pipeline configuration (databricks.yml).

-- ============ OT (historian / SCADA) ============
CREATE OR REFRESH STREAMING TABLE bronze_ot_historian
COMMENT 'OT: 1-minute historian tag values (long format), as exported by the plant historian.'
TBLPROPERTIES ('domain' = 'OT', 'source_system' = 'historian')
AS SELECT *, _metadata.file_path AS source_file, current_timestamp() AS ingested_at
FROM STREAM read_files('${raw_path}/ot/historian', format => 'csv', header => true,
                       schema => 'tag_name STRING, ts STRING, value STRING, quality STRING');

CREATE OR REFRESH STREAMING TABLE bronze_ot_machine_states
COMMENT 'OT: SCADA machine-state intervals (RUNNING / IDLE / SETUP / PLANNED_DOWN / UNPLANNED_DOWN).'
TBLPROPERTIES ('domain' = 'OT', 'source_system' = 'scada')
AS SELECT *, _metadata.file_path AS source_file, current_timestamp() AS ingested_at
FROM STREAM read_files('${raw_path}/ot/machine_states', format => 'json',
                       schema => 'equipment_path STRING, state STRING, reason_code STRING, start_ts STRING, end_ts STRING, source STRING');

CREATE OR REFRESH STREAMING TABLE bronze_ot_alarms
COMMENT 'OT: SCADA alarm events.'
TBLPROPERTIES ('domain' = 'OT', 'source_system' = 'scada')
AS SELECT *, _metadata.file_path AS source_file, current_timestamp() AS ingested_at
FROM STREAM read_files('${raw_path}/ot/alarms', format => 'json',
                       schema => 'equipment_path STRING, alarm_code STRING, severity STRING, alarm_ts STRING, value DOUBLE, message STRING');

-- ============ IT (ERP / MES / CMMS) ============
-- Master data arrives as full snapshots -> materialized views (re-read each update);
-- transactional extracts arrive as daily files -> streaming tables (append-only).
CREATE OR REFRESH MATERIALIZED VIEW bronze_it_assets
COMMENT 'IT: ERP equipment master, including historian_prefix (the IT<->OT key map).'
TBLPROPERTIES ('domain' = 'IT', 'source_system' = 'erp')
AS SELECT *, _metadata.file_path AS source_file, current_timestamp() AS ingested_at
FROM read_files('${raw_path}/it/assets', format => 'csv', header => true);

CREATE OR REFRESH MATERIALIZED VIEW bronze_it_shift_calendar
COMMENT 'IT: MES shift calendar.'
TBLPROPERTIES ('domain' = 'IT', 'source_system' = 'mes')
AS SELECT *, _metadata.file_path AS source_file, current_timestamp() AS ingested_at
FROM read_files('${raw_path}/it/shift_calendar', format => 'csv', header => true);

CREATE OR REFRESH MATERIALIZED VIEW bronze_it_operators (
  operator_id STRING, full_name STRING MASK ${uc_catalog}.${uc_schema}.mask_pii, badge_number STRING MASK ${uc_catalog}.${uc_schema}.mask_pii,
  crew STRING, certification_level STRING, source_file STRING, ingested_at TIMESTAMP
)
COMMENT 'IT: HR/MES operator roster. PII (full_name, badge_number) is masked by UC function mask_pii.'
TBLPROPERTIES ('domain' = 'IT', 'source_system' = 'mes', 'contains_pii' = 'true')
AS SELECT operator_id, full_name, badge_number, crew, certification_level,
  _metadata.file_path AS source_file, current_timestamp() AS ingested_at
FROM read_files('${raw_path}/it/operators', format => 'csv', header => true,
                schema => 'operator_id STRING, full_name STRING, badge_number STRING, crew STRING, certification_level STRING');

CREATE OR REFRESH STREAMING TABLE bronze_it_production_orders
COMMENT 'IT: ERP/MES production orders, one or two per asset per shift.'
TBLPROPERTIES ('domain' = 'IT', 'source_system' = 'erp')
AS SELECT *, _metadata.file_path AS source_file, current_timestamp() AS ingested_at
FROM STREAM read_files('${raw_path}/it/production_orders', format => 'csv', header => true);

CREATE OR REFRESH STREAMING TABLE bronze_it_production_confirmations
COMMENT 'IT: MES production confirmations (yield + scrap per order).'
TBLPROPERTIES ('domain' = 'IT', 'source_system' = 'mes')
AS SELECT *, _metadata.file_path AS source_file, current_timestamp() AS ingested_at
FROM STREAM read_files('${raw_path}/it/production_confirmations', format => 'csv', header => true,
                       schemaHints => 'yield_qty INT, scrap_qty INT');

CREATE OR REFRESH STREAMING TABLE bronze_it_work_orders
COMMENT 'IT: CMMS maintenance work orders (corrective + preventive).'
TBLPROPERTIES ('domain' = 'IT', 'source_system' = 'cmms')
AS SELECT *, _metadata.file_path AS source_file, current_timestamp() AS ingested_at
FROM STREAM read_files('${raw_path}/it/work_orders', format => 'csv', header => true, multiLine => true);
