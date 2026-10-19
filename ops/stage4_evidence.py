"""Regenerate evidence/07_lakebase.md: Lakebase project, forward synced tables, reverse CDF status, replicated rows, KPI view."""
import datetime, json, subprocess
from sql import run, table

S = "nraameast1_catalog.plant_floor_oee_febar"
PROJECT = "projects/plant-floor-oee-febar"
CDF = f"{PROJECT}/branches/production/databases/databricks-postgres/cdf-configs/ops_to_uc"

def cli(*args):
    return json.loads(subprocess.run(["databricks", *args, "-p", "fevm-nraameast1", "-o", "json"], capture_output=True, text=True, check=True).stdout)

proj = cli("postgres", "get-project", PROJECT)["status"]
ep = cli("postgres", "list-endpoints", f"{PROJECT}/branches/production")[0]
out = ["# Evidence 07 — Lakebase operational serving + reverse sync (live)", "",
       f"Generated {datetime.datetime.now():%Y-%m-%d %H:%M} by `ops/stage4_evidence.py`. Postgres-side output (DDL, replica identity, "
       "row counts, sub-millisecond point lookup, write-path smoke test) is in `06_lakebase_setup_run.ipynb`.", "",
       "## Project (resources/lakebase.yml)", "", "```",
       f"project:   {PROJECT}  (Postgres {proj['pg_version']}, autoscaling {proj['default_endpoint_settings']['autoscaling_limit_min_cu']}-"
       f"{proj['default_endpoint_settings']['autoscaling_limit_max_cu']} CU, suspend {proj['default_endpoint_settings'].get('suspend_timeout_duration')})",
       f"endpoint:  {ep['name']}  state={ep['status']['current_state']}", "```", "",
       "## Forward sync: Delta -> Postgres (synced tables)", "", "```"]
DECLARED = {"lb_at_risk_queue": "gold_at_risk_queue  pk=[asset_id]  TRIGGERED",       # resources/lakebase.yml
            "lb_oee_shift": "gold_oee_shift  pk=[asset_id, shift_id]  SNAPSHOT"}
for t, decl in DECLARED.items():
    st = cli("postgres", "get-synced-table", f"synced_tables/{S}.{t}")["status"]
    last = st.get("last_sync") or {}
    out.append(f"{t:18s} <- {decl}  state={st['detailed_state']}  pipeline={st.get('pipeline_id')}")
    out.append(f"{'':18s}    last_sync={json.dumps(last)[:220]}")
out += ["```", "", "## Reverse sync: Postgres schema `ops` -> Delta (change data feed config `ops_to_uc`)", "", "```"]
for s in cli("postgres", "list-cdf-statuses", CDF):
    out.append(f"{s['postgres_table']:22s} state={s['state']}  last_sync={s.get('last_sync_time')}")
out += ["```", "",
        "## Replicated change feed in Unity Catalog (lb_supervisor_actions_history)", "", "```",
        table(*run(f"SELECT _pg_change_type, _pg_lsn, _timestamp, action_id, asset_id, action, acted_by, acted_at FROM {S}.lb_supervisor_actions_history ORDER BY _pg_lsn, _sort_by")),
        "```", "",
        "## KPI view: alert -> first supervisor action (gold_alert_response, smoke tests excluded)", "", "```",
        table(*run(f"SELECT * FROM {S}.gold_alert_response ORDER BY risk_score DESC")), "```", ""]
open("evidence/07_lakebase.md", "w").write("\n".join(out))
print("wrote evidence/07_lakebase.md")
