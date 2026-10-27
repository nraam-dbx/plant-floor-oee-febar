"""Plant-floor OEE app (Stage 6).

Reads the at-risk queue and shift OEE from Lakebase Postgres (synced from the governed gold tables), writes supervisor
actions and work-order requests back to Lakebase (reverse-synced to Unity Catalog), and proxies chat to the Agent
Bricks Supervisor. Also exposes an MCP server at /mcp with a `request_work_order` tool so the Supervisor can raise a
work-order REQUEST that a person approves in this app.

Runs as the app's service principal; the signed-in user's email (X-Forwarded-Email) is recorded on every write.
"""
import contextlib, os, threading, time

import psycopg
from databricks.sdk import WorkspaceClient
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from mcp.server.fastmcp import FastMCP
from psycopg.rows import dict_row
from pydantic import BaseModel

w = WorkspaceClient()
ENDPOINT = os.environ["LAKEBASE_ENDPOINT"]
DATABASE = os.environ.get("LAKEBASE_DATABASE", "databricks_postgres")
SUPERVISOR = os.environ.get("SUPERVISOR_ENDPOINT", "")
SYNCED = "plant_floor_oee_febar"          # Postgres schema holding the synced (read-only) tables

_token = {"value": None, "expires": 0.0}
_lock = threading.Lock()


def _password():
    """Short-lived OAuth database credential for the app's service principal, refreshed every 30 min."""
    with _lock:
        if time.time() > _token["expires"]:
            _token["value"] = w.postgres.generate_database_credential(endpoint=ENDPOINT).token
            _token["expires"] = time.time() + 30 * 60
        return _token["value"]


def _host():
    if not hasattr(_host, "v"):
        _host.v = w.postgres.get_endpoint(ENDPOINT).status.hosts.host
    return _host.v


@contextlib.contextmanager
def db():
    conn = psycopg.connect(host=_host(), dbname=DATABASE, user=os.environ.get("PGUSER") or w.config.client_id,
                           password=_password(), sslmode="require", gssencmode="disable",
                           autocommit=True, row_factory=dict_row, connect_timeout=15)
    try:
        yield conn
    finally:
        conn.close()


def q(sql, params=None):
    with db() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall() if cur.description else []


def create_work_order_request(asset_id: str, requested_by: str, source: str, note: str = ""):
    """Insert a REQUESTED work order from the asset's AI draft, plus the matching supervisor action."""
    draft = q(f"SELECT * FROM {SYNCED}.lb_at_risk_queue WHERE upper(asset_id) = upper(%s)", (asset_id,))
    if not draft:
        raise HTTPException(404, f"unknown asset {asset_id}")
    d = draft[0]
    if not d["wo_problem_description"]:
        raise HTTPException(409, f"{d['asset_id']} is not at risk — there is no AI work-order draft to raise")
    with db() as conn, conn.cursor() as cur:
        cur.execute("""INSERT INTO ops.work_order_requests (asset_id, priority, problem_description, planned_tasks,
                         estimated_hours, source, requested_by)
                       VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING request_id, requested_at""",
                    (d["asset_id"], d["wo_priority"] or "P2", d["wo_problem_description"], d["wo_planned_tasks"],
                     d["wo_estimated_hours"], source, requested_by))
        wo = cur.fetchone()
        cur.execute("""INSERT INTO ops.supervisor_actions (asset_id, scored_shift_id, risk_score, action, note,
                         work_order_request_id, acted_by)
                       VALUES (%s, %s, %s, 'CREATE_WORK_ORDER', %s, %s, %s) RETURNING action_id""",
                    (d["asset_id"], d["scored_shift_id"], d["risk_score"], note or f"work order requested via {source.lower()}",
                     wo["request_id"], requested_by))
    return {"request_id": wo["request_id"], "asset_id": d["asset_id"], "priority": d["wo_priority"],
            "status": "REQUESTED", "requested_at": str(wo["requested_at"])}


# ---------------- MCP tool for the Supervisor agent ----------------
mcp = FastMCP("plant-floor-oee-actions", stateless_http=True)


@mcp.tool()
def request_work_order(asset_id: str, reason: str = "") -> dict:
    """Raise a work-order REQUEST for an at-risk asset from its AI-drafted work order. The request is created with
    status REQUESTED and must be approved by a supervisor in the plant-floor app before it goes to the CMMS.
    Use only when the user explicitly asks to raise / request / create a work order for a specific asset."""
    return create_work_order_request(asset_id, requested_by="supervisor-agent", source="AGENT", note=reason)


mcp_app = mcp.streamable_http_app()


@contextlib.asynccontextmanager
async def lifespan(_app):
    async with mcp.session_manager.run():
        yield


app = FastAPI(title="Plant-floor OEE", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")


def user(request: Request) -> str:
    return request.headers.get("X-Forwarded-Email") or request.headers.get("X-Forwarded-User") or "unknown-user"


@app.get("/")
def index():
    return FileResponse(os.path.join(os.path.dirname(__file__), "static", "index.html"))


@app.get("/api/summary")
def summary():
    oee = q(f"""SELECT round(avg(oee)::numeric * 100, 1) AS plant_oee_pct,
                       round(sum(unplanned_down_min)::numeric / 60, 1) AS unplanned_hours,
                       sum(scrap_qty) AS scrap_units, max(shift_date) AS through
                FROM {SYNCED}.lb_oee_shift
                WHERE shift_date > (SELECT max(shift_date) - 7 FROM {SYNCED}.lb_oee_shift)""")[0]
    risk = q(f"SELECT count(*) FILTER (WHERE at_risk) AS at_risk FROM {SYNCED}.lb_at_risk_queue")[0]
    wos = q("SELECT count(*) FILTER (WHERE status = 'REQUESTED') AS pending FROM ops.work_order_requests")[0]
    return {**oee, **risk, "pending_work_orders": wos["pending"]}


@app.get("/api/oee")
def oee_by_asset(days: int = 7):
    return q(f"""SELECT asset_id, work_center_name,
                   round(avg(availability)::numeric * 100, 1) AS availability, round(avg(performance)::numeric * 100, 1) AS performance,
                   round(avg(quality)::numeric * 100, 1) AS quality, round(avg(oee)::numeric * 100, 1) AS oee,
                   round(sum(unplanned_down_min)::numeric / 60, 1) AS unplanned_hours
                 FROM {SYNCED}.lb_oee_shift
                 WHERE shift_date > (SELECT max(shift_date) - %s FROM {SYNCED}.lb_oee_shift)
                 GROUP BY 1, 2 ORDER BY oee""", (days,))


@app.get("/api/queue")
def queue():
    rows = q(f"""SELECT r.*, a.action AS last_action, a.acted_by AS last_actor, a.acted_at AS last_acted_at
                 FROM {SYNCED}.lb_at_risk_queue r
                 LEFT JOIN LATERAL (SELECT action, acted_by, acted_at FROM ops.supervisor_actions s
                                    WHERE s.asset_id = r.asset_id AND s.scored_shift_id = r.scored_shift_id
                                      AND s.acted_by <> 'setup-smoke-test'
                                    ORDER BY acted_at DESC LIMIT 1) a ON true
                 ORDER BY r.risk_score DESC""")
    return rows


class Action(BaseModel):
    asset_id: str
    action: str
    note: str = ""


@app.post("/api/actions")
def take_action(body: Action, request: Request):
    if body.action == "CREATE_WORK_ORDER":
        return create_work_order_request(body.asset_id, user(request), "APP", body.note)
    if body.action not in ("ACKNOWLEDGE", "DEFER", "DISMISS"):
        raise HTTPException(400, "unknown action")
    if body.action in ("DEFER", "DISMISS") and not body.note.strip():
        raise HTTPException(400, "a reason is required to defer or dismiss (SOP-PLT-001)")
    r = q(f"SELECT scored_shift_id, risk_score FROM {SYNCED}.lb_at_risk_queue WHERE asset_id = %s", (body.asset_id,))
    if not r:
        raise HTTPException(404, "unknown asset")
    row = q("""INSERT INTO ops.supervisor_actions (asset_id, scored_shift_id, risk_score, action, note, acted_by)
               VALUES (%s, %s, %s, %s, %s, %s) RETURNING action_id, acted_at""",
            (body.asset_id, r[0]["scored_shift_id"], r[0]["risk_score"], body.action, body.note, user(request)))[0]
    return {"action_id": row["action_id"], "acted_at": str(row["acted_at"])}


@app.get("/api/work-orders")
def work_orders():
    return q("""SELECT request_id, asset_id, priority, status, source, requested_by, requested_at, estimated_hours,
                       left(problem_description, 160) AS problem
                FROM ops.work_order_requests ORDER BY requested_at DESC LIMIT 20""")


@app.post("/api/work-orders/{request_id}/approve")
def approve(request_id: int, request: Request):
    rows = q("""UPDATE ops.work_order_requests SET status = 'APPROVED', updated_at = now()
                WHERE request_id = %s AND status = 'REQUESTED' RETURNING request_id, status""", (request_id,))
    if not rows:
        raise HTTPException(409, "not in REQUESTED state")
    return rows[0]


class Chat(BaseModel):
    message: str = ""
    history: list[dict] = []          # prior user/assistant turns
    pending: list[dict] = []          # input items of a turn paused on an MCP approval request
    approval_id: str = ""
    approve: bool = False


def _invoke(items):
    try:
        return w.api_client.do("POST", f"/serving-endpoints/{SUPERVISOR}/invocations", body={"input": items})
    except Exception as e:                       # surface the agent's error instead of a bare 500
        raise HTTPException(502, f"agent call failed: {type(e).__name__}: {str(e)[:300]}")


@app.post("/api/chat")
def chat(body: Chat, request: Request):
    """One agent turn. If the Supervisor wants to call an app (MCP) tool it pauses with an mcp_approval_request;
    we return it to the UI, and the user's Approve/Reject comes back here as an mcp_approval_response."""
    t0 = time.time()
    if body.approval_id:
        items = body.pending + [{"type": "mcp_approval_response", "approval_request_id": body.approval_id,
                                 "approve": body.approve}]
    else:
        items = [m for m in body.history if m.get("role") in ("user", "assistant")][-8:] + \
                [{"role": "user", "content": body.message}]
    resp = _invoke(items)
    tools, texts, approval = [], [], None
    for item in resp.get("output", []):
        if item.get("type") == "function_call":
            tools.append(item.get("name", "").split("__")[-1])
        elif item.get("type") == "mcp_approval_request":
            approval = {"id": item["id"], "tool": item.get("name"), "arguments": item.get("arguments"),
                        "server": item.get("server_label")}
        elif item.get("type") == "message":
            texts += [c.get("text", "") for c in item.get("content", []) if c.get("text")]
    out = {"answer": texts[-1] if texts else "", "tools": tools, "seconds": round(time.time() - t0, 1)}
    if approval:
        out["approval"] = approval
        out["pending"] = items + resp.get("output", [])
        print(f"agent requested approval for {approval['tool']} {approval['arguments']} (user {user(request)})")
    elif body.approval_id:
        print(f"user {user(request)} {'approved' if body.approve else 'rejected'} {body.approval_id}")
    return out


@app.get("/api/health")
def health():
    return {"lakebase": q("SELECT 1 AS ok")[0]["ok"] == 1, "supervisor": SUPERVISOR}


app.mount("/", mcp_app)   # MCP streamable-HTTP endpoint at /mcp (mounted last so API routes win)
