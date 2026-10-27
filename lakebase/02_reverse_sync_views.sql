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
COMMENT 'Alert -> action latency: alert = risk published to the app queue (gold_at_risk_queue.published_at); first supervisor/agent action after it. Smoke tests excluded.'
AS WITH q AS (SELECT * FROM nraameast1_catalog.plant_floor_oee_febar.gold_at_risk_queue WHERE at_risk),
first_action AS (
  SELECT a.asset_id, a.scored_shift_id, min(a.acted_at) AS first_action_at,
         min_by(a.action, a.acted_at) AS first_action, min_by(a.acted_by, a.acted_at) AS first_actor, count(*) AS actions
  FROM nraameast1_catalog.plant_floor_oee_febar.gold_supervisor_actions a
  JOIN q ON q.asset_id = a.asset_id AND q.scored_shift_id = a.scored_shift_id AND a.acted_at >= q.published_at
  WHERE a.acted_by <> 'setup-smoke-test'
  GROUP BY ALL)
-- In production the alert time is the scored shift's end; this demo replays history, so it uses the publish time.
SELECT q.asset_id, q.scored_shift_id, q.risk_score, q.at_risk, q.published_at AS alert_raised_at,
  f.first_action, f.first_actor, f.first_action_at, f.actions,
  round(timestampdiff(SECOND, q.published_at, f.first_action_at) / 60.0, 1) AS minutes_to_first_action
FROM q LEFT JOIN first_action f ON f.asset_id = q.asset_id AND f.scored_shift_id = q.scored_shift_id;
