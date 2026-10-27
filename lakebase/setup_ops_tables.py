# Databricks notebook source
# MAGIC %md
# MAGIC # Stage 4 · Lakebase operational tables
# MAGIC Creates the writable `ops` schema in Lakebase Postgres (`lakebase/01_ops_schema.sql`) and shows what the
# MAGIC app reads: the forward-synced tables (Delta → Postgres) in schema `plant_floor_oee_febar`.
# MAGIC Auth: short-lived OAuth database credential for the run identity — no stored passwords.

# COMMAND ----------

# MAGIC %pip install -q "psycopg[binary]>=3.2" "databricks-sdk>=0.70"
# MAGIC %restart_python

# COMMAND ----------

dbutils.widgets.text("endpoint", "projects/plant-floor-oee-febar/branches/production/endpoints/primary")
dbutils.widgets.text("smoke_test", "true")
dbutils.widgets.text("app_role", "")   # app service principal client id -> least-privilege grants (03_app_grants.sql)
ENDPOINT = dbutils.widgets.get("endpoint")

import os, psycopg
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
host = w.postgres.get_endpoint(ENDPOINT).status.hosts.host
token = w.postgres.generate_database_credential(endpoint=ENDPOINT).token
user = w.current_user.me().user_name
conn = psycopg.connect(host=host, dbname="databricks_postgres", user=user, password=token, sslmode="require",
                       gssencmode="disable", autocommit=True)   # libpq GSSAPI probe aborts the process on serverless

def q(sql, params=None):
    with conn.cursor() as cur:
        cur.execute(sql, params)
        if cur.description:
            cols = [d.name for d in cur.description]
            rows = cur.fetchall()
            print(" | ".join(cols)); [print(" | ".join(str(v) for v in r)) for r in rows]
            return rows
        print("OK", cur.statusmessage)

print(f"connected to {host} as {user}")
q("SELECT version()")

# COMMAND ----------

ddl_path = os.path.join(os.path.dirname(dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()), "01_ops_schema.sql")
ddl = open("/Workspace" + ddl_path).read()
q(ddl)
q("""SELECT c.relname AS table_name, CASE c.relreplident WHEN 'f' THEN 'FULL' WHEN 'd' THEN 'DEFAULT' ELSE c.relreplident::text END AS replica_identity
     FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = 'ops' AND c.relkind = 'r' ORDER BY 1""")
q("""SELECT table_schema, table_name, (xpath('/row/c/text()', query_to_xml(format('select count(*) as c from %I.%I', table_schema, table_name), false, true, '')))[1]::text::int AS row_count
     FROM information_schema.tables WHERE table_schema IN ('ops', 'plant_floor_oee_febar') ORDER BY 1, 2""")

# COMMAND ----------

APP_ROLE = dbutils.widgets.get("app_role").strip()
if APP_ROLE:
    grants = open("/Workspace" + ddl_path.replace("01_ops_schema.sql", "03_app_grants.sql")).read().replace("{app_role}", APP_ROLE)
    q(grants)
    q("""SELECT table_schema, table_name, string_agg(privilege_type, ',' ORDER BY privilege_type) AS privileges
         FROM information_schema.role_table_grants WHERE grantee = %s GROUP BY 1, 2 ORDER BY 1, 2""", (APP_ROLE,))
    q("""SELECT table_name, column_name, privilege_type FROM information_schema.column_privileges
         WHERE grantee = %s AND privilege_type = 'UPDATE' ORDER BY 1, 2""", (APP_ROLE,))

# COMMAND ----------

# MAGIC %md ## What the app reads — forward-synced at-risk queue (Postgres, low-latency)

# COMMAND ----------

q("""SELECT asset_id, risk_score, at_risk, wo_priority, urgency, left(probable_cause, 80) AS probable_cause
     FROM plant_floor_oee_febar.lb_at_risk_queue ORDER BY risk_score DESC LIMIT 5""")
q("""EXPLAIN ANALYZE SELECT * FROM plant_floor_oee_febar.lb_at_risk_queue WHERE asset_id = 'CNC-02'""")

# COMMAND ----------

# MAGIC %md ## Smoke test of the write path (labelled; excluded from KPIs by `acted_by = 'setup-smoke-test'`)

# COMMAND ----------

if dbutils.widgets.get("smoke_test") == "true":
    q("""INSERT INTO ops.supervisor_actions (asset_id, scored_shift_id, risk_score, action, note, acted_by)
         SELECT asset_id, scored_shift_id, risk_score, 'ACKNOWLEDGE', 'setup smoke test of the Lakebase write path', 'setup-smoke-test'
         FROM plant_floor_oee_febar.lb_at_risk_queue ORDER BY risk_score DESC LIMIT 1
         RETURNING action_id, asset_id, action, acted_at""")
n = q("SELECT count(*) AS actions FROM ops.supervisor_actions")[0][0]
conn.close()
assert n >= 1, "write path check failed"   # fail the job loudly; a crashed kernel must never look like success
dbutils.notebook.exit(f"ok: {n} supervisor action rows")
