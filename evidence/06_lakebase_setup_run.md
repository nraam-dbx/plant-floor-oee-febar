# Evidence 06 — Lakebase Postgres: ops tables, app-role grants, low-latency read (job run)

Job task run `46438830195483` exported with outputs. Full run (all code + outputs): [`raw/06_lakebase_setup_run.ipynb`](raw/06_lakebase_setup_run.ipynb) · source: `lakebase/setup_ops_tables.py`.

# Stage 4 · Lakebase operational tables
Creates the writable `ops` schema in Lakebase Postgres (`lakebase/01_ops_schema.sql`) and shows what the
app reads: the forward-synced tables (Delta → Postgres) in schema `plant_floor_oee_febar`.
Auth: short-lived OAuth database credential for the run identity — no stored passwords.

```python
dbutils.widgets.text("endpoint", "projects/plant-floor-oee-febar/branches/production/endpoints/primary")
dbutils.widgets.text("smoke_test", "true")
dbutils.widgets.text("app_role", "")   # app service principal client id -> least-privilege grants (03_app_grants.sql)
ENDPOINT = dbutils.widgets.get("endpoint")

import os, psycopg
# … 21 more lines (see lakebase/setup_ops_tables.py)
```

Output:
```
connected to ep-wandering-wildflower-d24ysjzi.database.us-east-1.cloud.databricks.com as n.raam@databricks.com
version
PostgreSQL 17.11 (11592b3) on x86_64-pc-linux-gnu, compiled by gcc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0, 64-bit
```

```python
ddl_path = os.path.join(os.path.dirname(dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()), "01_ops_schema.sql")
ddl = open("/Workspace" + ddl_path).read()
q(ddl)
q("""SELECT c.relname AS table_name, CASE c.relreplident WHEN 'f' THEN 'FULL' WHEN 'd' THEN 'DEFAULT' ELSE c.relreplident::text END AS replica_identity
     FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = 'ops' AND c.relkind = 'r' ORDER BY 1""")
q("""SELECT table_schema, table_name, (xpath('/row/c/text()', query_to_xml(format('select count(*) as c from %I.%I', table_schema, table_name), false, true, '')))[1]::text::int AS row_count
# … 1 more lines (see lakebase/setup_ops_tables.py)
```

Output:
```
OK CREATE SCHEMA
table_name | replica_identity
supervisor_actions | FULL
work_order_requests | FULL
table_schema | table_name | row_count
ops | supervisor_actions | 4
ops | work_order_requests | 1
plant_floor_oee_febar | lb_at_risk_queue | 12
plant_floor_oee_febar | lb_oee_shift | 1008
```

```python
APP_ROLE = dbutils.widgets.get("app_role").strip()
if APP_ROLE:
    grants = open("/Workspace" + ddl_path.replace("01_ops_schema.sql", "03_app_grants.sql")).read().replace("{app_role}", APP_ROLE)
    q(grants)
    q("""SELECT table_schema, table_name, string_agg(privilege_type, ',' ORDER BY privilege_type) AS privileges
         FROM information_schema.role_table_grants WHERE grantee = %s GROUP BY 1, 2 ORDER BY 1, 2""", (APP_ROLE,))
# … 2 more lines (see lakebase/setup_ops_tables.py)
```

Output:
```
OK GRANT
table_schema | table_name | privileges
ops | supervisor_actions | INSERT,SELECT
ops | work_order_requests | INSERT,SELECT
plant_floor_oee_febar | lb_at_risk_queue | SELECT
plant_floor_oee_febar | lb_oee_shift | SELECT
table_name | column_name | privilege_type
work_order_requests | status | UPDATE
work_order_requests | updated_at | UPDATE
```

## What the app reads — forward-synced at-risk queue (Postgres, low-latency)

```python
q("""SELECT asset_id, risk_score, at_risk, wo_priority, urgency, left(probable_cause, 80) AS probable_cause
     FROM plant_floor_oee_febar.lb_at_risk_queue ORDER BY risk_score DESC LIMIT 5""")
q("""EXPLAIN ANALYZE SELECT * FROM plant_floor_oee_febar.lb_at_risk_queue WHERE asset_id = 'CNC-02'""")
```

Output:
```
asset_id | risk_score | at_risk | wo_priority | urgency | probable_cause
CNC-02 | 0.9981 | True | P2 | NEXT_PLANNED_STOP | Spindle bearing wear, most likely driven by lubrication starvation, consistent w
CNC-04 | 0.0682 | False | None | None | None
CMM-01 | 0.037 | False | None | None | None
GRD-02 | 0.0291 | False | None | None | None
WLD-01 | 0.0179 | False | None | None | None
QUERY PLAN
Seq Scan on partition_16749 lb_at_risk_queue  (cost=0.00..1.15 rows=1 width=1646) (actual time=0.008..0.009 rows=1 loops=1)
  Filter: (asset_id = 'CNC-02'::text)
  Rows Removed by Filter: 11
Planning Time: 0.125 ms
Execution Time: 0.024 ms
```

## Smoke test of the write path (labelled; excluded from KPIs by `acted_by = 'setup-smoke-test'`)

```python
if dbutils.widgets.get("smoke_test") == "true":
    q("""INSERT INTO ops.supervisor_actions (asset_id, scored_shift_id, risk_score, action, note, acted_by)
         SELECT asset_id, scored_shift_id, risk_score, 'ACKNOWLEDGE', 'setup smoke test of the Lakebase write path', 'setup-smoke-test'
         FROM plant_floor_oee_febar.lb_at_risk_queue ORDER BY risk_score DESC LIMIT 1
         RETURNING action_id, asset_id, action, acted_at""")
n = q("SELECT count(*) AS actions FROM ops.supervisor_actions")[0][0]
# … 3 more lines (see lakebase/setup_ops_tables.py)
```
