-- Stage 2 · Unity Catalog governance for the plant-floor OEE data products.
-- Run on the SQL warehouse: python3 ops/run_sql_file.py agents/01_governance.sql  (idempotent)
--   * one schema, two governed domains (IT / OT) expressed as UC tags, with owner + steward per domain
--   * PII (operator name, badge) masked by a UC function, applied as column masks inside the pipeline
--   * access grants are NOT applied here (pending decision on which principals get gold read access)
-- Group referenced: plant_hr_admins (workspace group, created 2026-10-19; members may unmask PII). Empty = everyone masked.

USE CATALOG nraameast1_catalog;
USE SCHEMA plant_floor_oee_febar;

-- ---------- PII masking ----------
CREATE OR REPLACE FUNCTION mask_pii(value STRING)
RETURNS STRING
COMMENT 'Column mask for operator PII: plant_hr_admins see the value, everyone else sees an initial + ***.'
RETURN CASE WHEN is_member('plant_hr_admins') THEN value   -- workspace group (FEVM: no account-console access)
            WHEN value IS NULL THEN NULL
            ELSE concat(left(value, 1), '***') END;

-- ---------- schema + domain tags ----------
-- Keys are prefixed oee_ to stay clear of workspace-wide governed tag policies; data_product and
-- system.certification_status use the governed keys with allowed values.
ALTER SCHEMA plant_floor_oee_febar SET TAGS ('data_product' = 'analytics', 'oee_data_product' = 'plant_floor_oee');

-- OT domain (historian / SCADA): owner controls engineering, steward reliability engineering.
ALTER STREAMING TABLE bronze_ot_historian SET TAGS ('oee_domain' = 'OT', 'oee_layer' = 'bronze', 'oee_source_system' = 'historian', 'oee_data_owner' = 'controls_engineering', 'oee_data_steward' = 'reliability_engineering');
ALTER STREAMING TABLE bronze_ot_machine_states SET TAGS ('oee_domain' = 'OT', 'oee_layer' = 'bronze', 'oee_source_system' = 'scada', 'oee_data_owner' = 'controls_engineering', 'oee_data_steward' = 'reliability_engineering');
ALTER STREAMING TABLE bronze_ot_alarms SET TAGS ('oee_domain' = 'OT', 'oee_layer' = 'bronze', 'oee_source_system' = 'scada', 'oee_data_owner' = 'controls_engineering', 'oee_data_steward' = 'reliability_engineering');
ALTER STREAMING TABLE silver_ot_historian SET TAGS ('oee_domain' = 'OT', 'oee_layer' = 'silver', 'oee_data_owner' = 'controls_engineering', 'oee_data_steward' = 'reliability_engineering');
ALTER MATERIALIZED VIEW silver_ot_tag_minute SET TAGS ('oee_domain' = 'OT', 'oee_layer' = 'silver', 'oee_data_owner' = 'controls_engineering', 'oee_data_steward' = 'reliability_engineering');
ALTER STREAMING TABLE silver_ot_machine_states SET TAGS ('oee_domain' = 'OT', 'oee_layer' = 'silver', 'oee_data_owner' = 'controls_engineering', 'oee_data_steward' = 'reliability_engineering');
ALTER STREAMING TABLE silver_ot_alarms SET TAGS ('oee_domain' = 'OT', 'oee_layer' = 'silver', 'oee_data_owner' = 'controls_engineering', 'oee_data_steward' = 'reliability_engineering');

-- IT domain (ERP / MES / CMMS / HR): owner manufacturing IT, steward per business process.
ALTER MATERIALIZED VIEW bronze_it_assets SET TAGS ('oee_domain' = 'IT', 'oee_layer' = 'bronze', 'oee_source_system' = 'erp', 'oee_data_owner' = 'manufacturing_it', 'oee_data_steward' = 'production_planning');
ALTER MATERIALIZED VIEW bronze_it_shift_calendar SET TAGS ('oee_domain' = 'IT', 'oee_layer' = 'bronze', 'oee_source_system' = 'mes', 'oee_data_owner' = 'manufacturing_it', 'oee_data_steward' = 'production_planning');
ALTER MATERIALIZED VIEW bronze_it_operators SET TAGS ('oee_domain' = 'IT', 'oee_layer' = 'bronze', 'oee_source_system' = 'mes', 'oee_pii' = 'true', 'oee_data_owner' = 'manufacturing_it', 'oee_data_steward' = 'plant_hr');
ALTER STREAMING TABLE bronze_it_production_orders SET TAGS ('oee_domain' = 'IT', 'oee_layer' = 'bronze', 'oee_source_system' = 'erp', 'oee_data_owner' = 'manufacturing_it', 'oee_data_steward' = 'production_planning');
ALTER STREAMING TABLE bronze_it_production_confirmations SET TAGS ('oee_domain' = 'IT', 'oee_layer' = 'bronze', 'oee_source_system' = 'mes', 'oee_data_owner' = 'manufacturing_it', 'oee_data_steward' = 'production_planning');
ALTER STREAMING TABLE bronze_it_work_orders SET TAGS ('oee_domain' = 'IT', 'oee_layer' = 'bronze', 'oee_source_system' = 'cmms', 'oee_data_owner' = 'manufacturing_it', 'oee_data_steward' = 'maintenance_planning');
ALTER MATERIALIZED VIEW silver_assets SET TAGS ('oee_domain' = 'IT', 'oee_layer' = 'silver', 'it_ot_key_map' = 'true', 'oee_data_owner' = 'manufacturing_it', 'oee_data_steward' = 'production_planning');
ALTER MATERIALIZED VIEW silver_shift_calendar SET TAGS ('oee_domain' = 'IT', 'oee_layer' = 'silver', 'oee_data_owner' = 'manufacturing_it', 'oee_data_steward' = 'production_planning');
ALTER MATERIALIZED VIEW silver_operators SET TAGS ('oee_domain' = 'IT', 'oee_layer' = 'silver', 'oee_pii' = 'true', 'oee_data_owner' = 'manufacturing_it', 'oee_data_steward' = 'plant_hr');
ALTER STREAMING TABLE silver_production_orders SET TAGS ('oee_domain' = 'IT', 'oee_layer' = 'silver', 'oee_data_owner' = 'manufacturing_it', 'oee_data_steward' = 'production_planning');
ALTER STREAMING TABLE silver_production_confirmations SET TAGS ('oee_domain' = 'IT', 'oee_layer' = 'silver', 'oee_data_owner' = 'manufacturing_it', 'oee_data_steward' = 'production_planning');
ALTER STREAMING TABLE silver_work_orders SET TAGS ('oee_domain' = 'IT', 'oee_layer' = 'silver', 'oee_data_owner' = 'manufacturing_it', 'oee_data_steward' = 'maintenance_planning');

-- Gold: integrated IT+OT data products, owned by plant operations excellence.
ALTER MATERIALIZED VIEW gold_asset_shift_time SET TAGS ('oee_domain' = 'IT_OT', 'oee_layer' = 'gold', 'oee_data_owner' = 'operations_excellence', 'oee_data_steward' = 'plant_performance', 'system.certification_status' = 'certified');
ALTER MATERIALIZED VIEW gold_ot_cycles_shift SET TAGS ('oee_domain' = 'IT_OT', 'oee_layer' = 'gold', 'oee_data_owner' = 'operations_excellence', 'oee_data_steward' = 'plant_performance');
ALTER MATERIALIZED VIEW gold_oee_shift SET TAGS ('oee_domain' = 'IT_OT', 'oee_layer' = 'gold', 'oee_data_owner' = 'operations_excellence', 'oee_data_steward' = 'plant_performance', 'system.certification_status' = 'certified', 'kpi' = 'oee');
ALTER MATERIALIZED VIEW gold_downtime_events SET TAGS ('oee_domain' = 'IT_OT', 'oee_layer' = 'gold', 'oee_data_owner' = 'operations_excellence', 'oee_data_steward' = 'reliability_engineering', 'system.certification_status' = 'certified', 'kpi' = 'mttr');
ALTER MATERIALIZED VIEW gold_asset_reliability SET TAGS ('oee_domain' = 'IT_OT', 'oee_layer' = 'gold', 'oee_data_owner' = 'operations_excellence', 'oee_data_steward' = 'reliability_engineering', 'system.certification_status' = 'certified', 'kpi' = 'mtbf');
ALTER MATERIALIZED VIEW gold_shift_features SET TAGS ('oee_domain' = 'IT_OT', 'oee_layer' = 'gold', 'oee_data_owner' = 'operations_excellence', 'oee_data_steward' = 'data_science', 'ml_feature_table' = 'true');

ALTER VOLUME raw SET TAGS ('oee_domain' = 'IT_OT', 'oee_layer' = 'landing', 'oee_data_owner' = 'data_engineering');

-- ---------- access by role (DESIGN — not applied in the FEVM demo workspace) ----------
-- Unity Catalog grants need ACCOUNT-level groups; the build user is not an account admin on the FEVM account,
-- so these groups can't be created here. In a customer account, create them in the account console, then run:
--
--   GRANT USE CATALOG ON CATALOG nraameast1_catalog TO `plant_ops_analysts`;
--   GRANT USE SCHEMA ON SCHEMA plant_floor_oee_febar TO `plant_ops_analysts`;
--   GRANT SELECT ON TABLE gold_oee_shift, gold_downtime_events, gold_asset_reliability,
--                         gold_asset_shift_time, silver_assets TO `plant_ops_analysts`;   -- one GRANT per table
--
--   reliability_engineers: everything plant_ops_analysts has, plus SELECT on
--     silver_ot_historian, silver_ot_tag_minute, silver_ot_alarms, silver_ot_machine_states, silver_work_orders
--
--   plant_data_science: USE SCHEMA, SELECT on gold_shift_features + silver_ot_*, CREATE MODEL, CREATE FUNCTION
--   plant_data_engineering: schema owner (bronze, silver, raw volume); runs the pipeline
--   plant_hr_admins: no table grants — membership only unmasks operator PII via mask_pii
--
-- Decision (2026-10-19): no account admin -> grant UC privileges directly to account-level identities only:
-- service principals (App, agents) and, if needed, named users. No `account users` grant.
-- Runtime identities (App service principal, agent run-as) get real least-privilege grants in their own stage
-- scripts (Lakebase / agents / app), since service principals can be created and granted from the workspace.

-- ---------- Stage 3-4 tables: model outputs, Lakebase synced + reverse-synced tables ----------
ALTER TABLE gold_asset_risk          SET TAGS ('oee_domain' = 'IT_OT', 'oee_layer' = 'gold', 'oee_data_owner' = 'operations_excellence', 'oee_data_steward' = 'data_science', 'oee_ml_output' = 'oee_at_risk_model');
ALTER TABLE gold_asset_risk_insights SET TAGS ('oee_domain' = 'IT_OT', 'oee_layer' = 'gold', 'oee_data_owner' = 'operations_excellence', 'oee_data_steward' = 'reliability_engineering', 'oee_genai_output' = 'true');
ALTER TABLE gold_at_risk_queue       SET TAGS ('oee_domain' = 'IT_OT', 'oee_layer' = 'gold', 'oee_data_owner' = 'operations_excellence', 'oee_data_steward' = 'plant_performance', 'oee_served_by' = 'lakebase');
ALTER TABLE lb_supervisor_actions_history  SET TAGS ('oee_domain' = 'IT_OT', 'oee_layer' = 'operational', 'oee_data_owner' = 'operations_excellence', 'oee_source_system' = 'lakebase_app', 'oee_sync' = 'reverse_cdf');
ALTER TABLE lb_work_order_requests_history SET TAGS ('oee_domain' = 'IT_OT', 'oee_layer' = 'operational', 'oee_data_owner' = 'operations_excellence', 'oee_source_system' = 'lakebase_app', 'oee_sync' = 'reverse_cdf');
