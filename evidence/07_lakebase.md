# Evidence 07 — Lakebase operational serving + reverse sync (live)

Generated 2026-10-19 15:52 by `ops/stage4_evidence.py`. Postgres-side output (DDL, replica identity, row counts, sub-millisecond point lookup, write-path smoke test) is in `06_lakebase_setup_run.ipynb`.

## Project (resources/lakebase.yml)

```
project:   projects/plant-floor-oee-febar  (Postgres 17, autoscaling 0.5-2 CU, suspend 300s)
endpoint:  projects/plant-floor-oee-febar/branches/production/endpoints/primary  state=ACTIVE
```

## Forward sync: Delta -> Postgres (synced tables)

```
lb_at_risk_queue   <- gold_at_risk_queue  pk=[asset_id]  TRIGGERED  state=SYNCED_TABLE_ONLINE_NO_PENDING_UPDATE  pipeline=9f055bcd-cba7-4cfc-837f-1528eafd8d06
                      last_sync={"delta_table_sync_info": {"delta_commit_time": "2026-10-19T19:13:39Z", "delta_commit_version": 0}, "sync_end_time": "2026-10-19T19:15:03.261857Z", "sync_start_time": "2026-10-19T19:14:52.422096Z"}
lb_oee_shift       <- gold_oee_shift  pk=[asset_id, shift_id]  SNAPSHOT  state=SYNCED_TABLE_ONLINE_NO_PENDING_UPDATE  pipeline=08438a71-4779-40d9-b3f8-9e2ee010c936
                      last_sync={"delta_table_sync_info": {"delta_commit_time": "1970-01-01T00:00:00Z", "delta_commit_version": 7}, "sync_end_time": "2026-10-19T19:15:00.143527Z", "sync_start_time": "2026-10-19T19:14:49.336311Z"}
```

## Reverse sync: Postgres schema `ops` -> Delta (change data feed config `ops_to_uc`)

```
supervisor_actions     state=CDF_STATE_STREAMING  last_sync=2026-10-19T19:46:31.871718Z
work_order_requests    state=CDF_STATE_STREAMING  last_sync=2026-10-19T19:46:33.649923Z
```

## Replicated change feed in Unity Catalog (lb_supervisor_actions_history)

```
_pg_change_type | _pg_lsn  | _timestamp              | action_id | asset_id | action      | acted_by         | acted_at                
----------------+----------+-------------------------+-----------+----------+-------------+------------------+-------------------------
insert          | 30499000 | 2026-10-19T19:46:31.721 | 1         | CNC-02   | ACKNOWLEDGE | setup-smoke-test | 2026-10-19T19:17:26.956Z
insert          | 30499000 | 2026-10-19T19:46:31.721 | 2         | CNC-02   | ACKNOWLEDGE | setup-smoke-test | 2026-10-19T19:18:47.925Z
```

## KPI view: alert -> first supervisor action (gold_alert_response, smoke tests excluded)

```
asset_id | scored_shift_id | risk_score | at_risk | alert_raised_at          | first_action | first_action_at | actions | minutes_to_first_action
---------+-----------------+------------+---------+--------------------------+--------------+-----------------+---------+------------------------
CNC-02   | 2026-10-18-C    | 0.9981     | true    | 2026-10-19T06:00:00.000Z | None         | None            | None    | None                   
```
