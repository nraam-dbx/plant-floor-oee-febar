-- Stage 4 · Views over the reverse-synced Lakebase change feed (lb_*_history, written by CDF config ops_to_uc).
-- The history tables hold every insert/update/delete with its Postgres LSN; these views give current state + KPIs.

CREATE OR REPLACE VIEW nraameast1_catalog.plant_floor_oee_febar.gold_supervisor_actions
COMMENT 'Current state of supervisor actions taken in the app (latest change per action_id from the Lakebase change feed).'
AS SELECT * EXCEPT (_pg_change_type, _pg_lsn, _pg_xid, _sort_by, rn) FROM (
  SELECT *, row_number() OVER (PARTITION BY action_id ORDER BY _pg_lsn DESC, _sort_by DESC) AS rn
  FROM nraameast1_catalog.plant_floor_oee_febar.lb_supervisor_actions_history)
WHERE rn = 1 AND _pg_change_type <> 'delete';

CREATE OR REPLACE VIEW nraameast1_catalog.plant_floor_oee_febar.gold_work_order_requests
COMMENT 'Current state of work-order requests raised from the app or the agent (latest change per request_id).'
AS SELECT * EXCEPT (_pg_change_type, _pg_lsn, _pg_xid, _sort_by, rn) FROM (
  SELECT *, row_number() OVER (PARTITION BY request_id ORDER BY _pg_lsn DESC, _sort_by DESC) AS rn
  FROM nraameast1_catalog.plant_floor_oee_febar.lb_work_order_requests_history)
WHERE rn = 1 AND _pg_change_type <> 'delete';

CREATE OR REPLACE VIEW nraameast1_catalog.plant_floor_oee_febar.gold_alert_response
COMMENT 'Alert -> action latency: risk alert raised at the end of the scored shift; first supervisor action on it. Smoke tests excluded.'
AS WITH first_action AS (
  SELECT asset_id, scored_shift_id, min(acted_at) AS first_action_at,
         min_by(action, acted_at) AS first_action, count(*) AS actions
  FROM nraameast1_catalog.plant_floor_oee_febar.gold_supervisor_actions
  WHERE acted_by <> 'setup-smoke-test'
  GROUP BY ALL)
SELECT q.asset_id, q.scored_shift_id, q.risk_score, q.at_risk, s.shift_end AS alert_raised_at,
  f.first_action, f.first_action_at, f.actions,
  round(timestampdiff(SECOND, s.shift_end, f.first_action_at) / 60.0, 1) AS minutes_to_first_action
FROM nraameast1_catalog.plant_floor_oee_febar.gold_at_risk_queue q
JOIN nraameast1_catalog.plant_floor_oee_febar.silver_shift_calendar s ON s.shift_id = q.scored_shift_id
LEFT JOIN first_action f ON f.asset_id = q.asset_id AND f.scored_shift_id = q.scored_shift_id
WHERE q.at_risk;
