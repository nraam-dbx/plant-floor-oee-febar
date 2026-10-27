# Evidence 07 — Lakebase operational serving + reverse sync (live)

Generated 2026-10-27 17:48 by `ops/stage4_evidence.py`. Postgres-side output (DDL, replica identity, row counts, sub-millisecond point lookup, write-path smoke test) is in `06_lakebase_setup_run.ipynb`.

## Project (resources/lakebase.yml)

```
project:   projects/plant-floor-oee-febar  (Postgres 17, autoscaling 0.5-2 CU, suspend 300s)
endpoint:  projects/plant-floor-oee-febar/branches/production/endpoints/primary  state=ACTIVE
```

## Forward sync: Delta -> Postgres (synced tables)

```
lb_at_risk_queue   <- gold_at_risk_queue  pk=[asset_id]  TRIGGERED  state=SYNCED_TABLE_ONLINE_NO_PENDING_UPDATE  pipeline=9f055bcd-cba7-4cfc-837f-1528eafd8d06
                      last_sync={"delta_table_sync_info": {"delta_commit_time": "2026-10-27T21:42:53Z", "delta_commit_version": 3}, "sync_end_time": "2026-10-27T21:43:47.019797Z", "sync_start_time": "2026-10-27T21:43:45.095752Z"}
lb_oee_shift       <- gold_oee_shift  pk=[asset_id, shift_id]  SNAPSHOT  state=SYNCED_TABLE_ONLINE_NO_PENDING_UPDATE  pipeline=08438a71-4779-40d9-b3f8-9e2ee010c936
                      last_sync={"delta_table_sync_info": {"delta_commit_time": "1970-01-01T00:00:00Z", "delta_commit_version": 11}, "sync_end_time": "2026-10-27T21:26:39.300497Z", "sync_start_time": "2026-10-27T21:26:29.613392Z"}
```

## Reverse sync: Postgres schema `ops` -> Delta (change data feed config `ops_to_uc`)

```
supervisor_actions     state=CDF_STATE_STREAMING  last_sync=2026-10-27T21:45:00.990143Z
work_order_requests    state=CDF_STATE_STREAMING  last_sync=2026-10-27T21:04:44.357050Z
```

## Replicated change feed in Unity Catalog (lb_supervisor_actions_history)

```
_pg_change_type | _pg_lsn  | _timestamp              | action_id | asset_id | action            | acted_by              | acted_at                
----------------+----------+-------------------------+-----------+----------+-------------------+-----------------------+-------------------------
insert          | 30499000 | 2026-10-19T19:46:31.721 | 1         | CNC-02   | ACKNOWLEDGE       | setup-smoke-test      | 2026-10-19T19:17:26.956Z
insert          | 30499000 | 2026-10-19T19:46:31.721 | 2         | CNC-02   | ACKNOWLEDGE       | setup-smoke-test      | 2026-10-19T19:18:47.925Z
insert          | 32559592 | 2026-10-27T21:00:21.185 | 3         | CNC-02   | CREATE_WORK_ORDER | supervisor-agent      | 2026-10-27T21:00:20.048Z
insert          | 32684968 | 2026-10-27T21:04:35.489 | 4         | CNC-02   | ACKNOWLEDGE       | n.raam@databricks.com | 2026-10-27T21:04:35.488Z
insert          | 34468832 | 2026-10-27T21:44:53.054 | 5         | CNC-02   | ACKNOWLEDGE       | n.raam@databricks.com | 2026-10-27T21:44:52.431Z
```

## KPI view: alert -> first supervisor action (gold_alert_response, smoke tests excluded)

```
asset_id | scored_shift_id | risk_score | at_risk | alert_raised_at          | first_action | first_actor           | first_action_at          | actions | minutes_to_first_action
---------+-----------------+------------+---------+--------------------------+--------------+-----------------------+--------------------------+---------+------------------------
CNC-02   | 2026-10-18-C    | 0.9981     | true    | 2026-10-27T21:42:46.600Z | ACKNOWLEDGE  | n.raam@databricks.com | 2026-10-27T21:44:52.431Z | 1       | 2.1                    
```
