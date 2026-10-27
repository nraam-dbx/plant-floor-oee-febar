"""Regenerate evidence/10_app.md: the app's least-privilege resources, live API output (read as the app's service
principal from Lakebase), an agent chat answer via the app, and the closed loop in Unity Catalog (reverse-synced actions,
work-order history, alert -> action KPI). Uses the caller's OAuth token to call the app."""
import datetime, json, subprocess, urllib.request
from sql import run, table

PROFILE, APP = "fevm-nraameast1", "plant-floor-oee-febar"
S = "nraameast1_catalog.plant_floor_oee_febar"

def cli(*args):
    return json.loads(subprocess.run(["databricks", *args, "-p", PROFILE, "-o", "json"], capture_output=True, text=True, check=True).stdout)

app = cli("apps", "get", APP)
token = cli("auth", "token")["access_token"]
def call(path, body=None, timeout=240):
    req = urllib.request.Request(app["url"] + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())

out = ["# Evidence 10 — Databricks App: plant-floor OEE board, actions, agent chat (live)", "",
       f"Generated {datetime.datetime.now():%Y-%m-%d %H:%M} by `ops/stage6_evidence.py`. App `{APP}` "
       f"(compute {app['compute_status']['state']}, app {app['app_status']['state']}) — {app['url']}", "",
       f"## Least-privilege grants to the app's service principal `{app['service_principal_client_id']}` (resources/app.yml)", "", "```"]
for r in app.get("resources", []):
    kind = next(k for k in r if k not in ("name", "description"))
    spec = r[kind]
    target = spec.get("securable_full_name") or spec.get("name") or spec.get("space_id") or spec.get("id") or spec.get("branch")
    out.append(f"{r['name']:28s} {kind:16s} {spec.get('permission', ''):24s} {target}")
perms = cli("apps", "get-permissions", APP)
out += [f"{'app (own MCP endpoint)':28s} {'app':16s} {'CAN_USE':24s} granted so the Supervisor can call /mcp as this SP"
        for a in perms.get("access_control_list", []) if a.get("service_principal_name") == app["service_principal_client_id"]]
out += ["```", "", "Postgres-side grants for the same role (lakebase/03_app_grants.sql): SELECT on the synced tables, "
        "SELECT+INSERT on ops.supervisor_actions / ops.work_order_requests, UPDATE(status, updated_at) only — see "
        "`11_app_grants_run.ipynb`.", "",
        "## App API (served from Lakebase as the app's service principal)", "", "```",
        "GET /api/health   " + json.dumps(call("/api/health")),
        "GET /api/summary  " + json.dumps(call("/api/summary"))]
qrow = call("/api/queue")[0]
out += ["GET /api/queue    top row: " + json.dumps({k: qrow[k] for k in ("asset_id", "risk_score", "at_risk", "wo_priority", "urgency", "last_action", "last_actor")}),
        "GET /api/work-orders  " + json.dumps([{k: w[k] for k in ("request_id", "asset_id", "priority", "status", "source", "requested_by")} for w in call("/api/work-orders")]),
        "```", ""]
q = "Which work center had the lowest average OEE last week, and what was the biggest loss?"
r = call("/api/chat", {"message": q})
out += [f"## Agent chat through the app — \"{q}\"", "", f"Tools: `{' -> '.join(r['tools'])}` · {r['seconds']} s", "", "```", r["answer"], "```", "",
        "## Agent-raised work order with human approval (MCP tool on this app)", "",
        "The Supervisor's `request_work_order` tool is the app's MCP server. Agent Bricks pauses the call with an "
        "`mcp_approval_request`; the app shows Approve/Reject; only on Approve does the tool run, creating a REQUESTED work "
        "order that a supervisor then approves in the app. Work-order history as reverse-synced to Unity Catalog:", "", "```",
        table(*run(f"SELECT _pg_change_type, request_id, asset_id, priority, status, source, requested_by, updated_at FROM {S}.lb_work_order_requests_history ORDER BY _pg_lsn, _sort_by")),
        "```", "", "## Supervisor actions (gold_supervisor_actions, reverse-synced from Lakebase)", "", "```",
        table(*run(f"SELECT action_id, asset_id, action, acted_by, acted_at, work_order_request_id, left(note, 60) note FROM {S}.gold_supervisor_actions ORDER BY action_id")),
        "```", "", "## KPI — alert -> first action (gold_alert_response)", "", "```",
        table(*run(f"SELECT * FROM {S}.gold_alert_response")), "```", ""]
open("evidence/10_app.md", "w").write("\n".join(out))
print("wrote evidence/10_app.md")
