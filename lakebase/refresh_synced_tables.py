# Databricks notebook source
# MAGIC %md
# MAGIC # Stage 4 · Refresh Lakebase synced tables after a build
# MAGIC `lb_at_risk_queue` (TRIGGERED) and `lb_oee_shift` (SNAPSHOT) only move when their sync pipeline runs; this task
# MAGIC triggers both after the model + GenAI tasks republish the gold tables, and waits for them to finish.

# COMMAND ----------

dbutils.widgets.text("synced_tables", "nraameast1_catalog.plant_floor_oee_febar.lb_at_risk_queue,nraameast1_catalog.plant_floor_oee_febar.lb_oee_shift")
import time
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
started = {}
for t in dbutils.widgets.get("synced_tables").split(","):
    pid = w.api_client.do("GET", f"/api/2.0/postgres/synced_tables/{t}")["status"]["pipeline_id"]
    started[t] = (pid, w.pipelines.start_update(pid).update_id)
    print(f"{t}: started update {started[t][1]} on pipeline {pid}")

for t, (pid, uid) in started.items():
    while (state := w.pipelines.get_update(pid, uid).update.state.value) not in ("COMPLETED", "FAILED", "CANCELED"):
        time.sleep(10)
    print(f"{t}: {state}")
    assert state == "COMPLETED", f"sync of {t} ended {state}"
