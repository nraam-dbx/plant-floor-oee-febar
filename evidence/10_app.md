# Evidence 10 — Databricks App: plant-floor OEE board, actions, agent chat (live)

Generated 2026-10-27 17:51 by `ops/stage6_evidence.py`. App `plant-floor-oee-febar` (compute ACTIVE, app RUNNING) — https://plant-floor-oee-febar-7474650251978703.aws.databricksapps.com

## Least-privilege grants to the app's service principal `29d0fd28-7036-4e25-9405-51d06b07d682` (resources/app.yml)

```
lakebase                     postgres         CAN_CONNECT_AND_CREATE   projects/plant-floor-oee-febar/branches/production
supervisor_endpoint          serving_endpoint CAN_QUERY                mas-9960e05a-endpoint
knowledge_assistant_endpoint serving_endpoint CAN_QUERY                ka-fedb6b90-endpoint
genie_space                  genie_space      CAN_RUN                  Plant OEE Analyst
sql_warehouse                sql_warehouse    CAN_USE                  ba24ff79986686a9
fn_get_asset_risk            uc_securable     EXECUTE                  nraameast1_catalog.plant_floor_oee_febar.get_asset_risk
fn_get_work_order_draft      uc_securable     EXECUTE                  nraameast1_catalog.plant_floor_oee_febar.get_work_order_draft
tbl_at_risk_queue            uc_securable     SELECT                   nraameast1_catalog.plant_floor_oee_febar.gold_at_risk_queue
tbl_oee_shift                uc_securable     SELECT                   nraameast1_catalog.plant_floor_oee_febar.gold_oee_shift
tbl_downtime_events          uc_securable     SELECT                   nraameast1_catalog.plant_floor_oee_febar.gold_downtime_events
tbl_asset_reliability        uc_securable     SELECT                   nraameast1_catalog.plant_floor_oee_febar.gold_asset_reliability
tbl_alert_response           uc_securable     SELECT                   nraameast1_catalog.plant_floor_oee_febar.gold_alert_response
tbl_assets                   uc_securable     SELECT                   nraameast1_catalog.plant_floor_oee_febar.silver_assets
tbl_work_orders              uc_securable     SELECT                   nraameast1_catalog.plant_floor_oee_febar.silver_work_orders
app (own MCP endpoint)       app              CAN_USE                  granted so the Supervisor can call /mcp as this SP
```

Postgres-side grants for the same role (lakebase/03_app_grants.sql): SELECT on the synced tables, SELECT+INSERT on ops.supervisor_actions / ops.work_order_requests, UPDATE(status, updated_at) only — see `11_app_grants_run.ipynb`.

## App API (served from Lakebase as the app's service principal)

```
GET /api/health   {"lakebase": true, "supervisor": "mas-9960e05a-endpoint"}
GET /api/summary  {"plant_oee_pct": 73.7, "unplanned_hours": 39.5, "scrap_units": 493, "through": "2026-10-18", "at_risk": 1, "pending_work_orders": 0}
GET /api/queue    top row: {"asset_id": "CNC-02", "risk_score": 0.9981, "at_risk": true, "wo_priority": "P1", "urgency": "IMMEDIATE", "last_action": "ACKNOWLEDGE", "last_actor": "n.raam@databricks.com"}
GET /api/work-orders  [{"request_id": 1, "asset_id": "CNC-02", "priority": "P1", "status": "APPROVED", "source": "AGENT", "requested_by": "supervisor-agent"}]
```

## Agent chat through the app — "Which work center had the lowest average OEE last week, and what was the biggest loss?"

Tools: `plant_oee_analyst` · 38.2 s

```
**WC_GRND** (Grinding work center) had the lowest average OEE last week at **70.10%**.

The biggest loss was **performance loss at 19.34 percentage points**, followed by availability loss at 10.15 percentage points and quality loss at 3.57 percentage points.

The grinding work center averaged:
- **89.85%** availability (10.15 pp loss from ideal)
- **80.66%** performance (19.34 pp loss from ideal)
- **96.43%** quality (3.57 pp loss from ideal)

Supporting metrics show an average of 11.1 minutes of unplanned downtime per shift, 35.1 minutes of setup time, 4.4 minor stops, and 3.6 units of scrap.
```

## Agent-raised work order with human approval (MCP tool on this app)

The Supervisor's `request_work_order` tool is the app's MCP server. Agent Bricks pauses the call with an `mcp_approval_request`; the app shows Approve/Reject; only on Approve does the tool run, creating a REQUESTED work order that a supervisor then approves in the app. Work-order history as reverse-synced to Unity Catalog:

```
_pg_change_type  | request_id | asset_id | priority | status    | source | requested_by     | updated_at              
-----------------+------------+----------+----------+-----------+--------+------------------+-------------------------
insert           | 1          | CNC-02   | P1       | REQUESTED | AGENT  | supervisor-agent | 2026-10-27T21:00:20.025Z
update_preimage  | 1          | CNC-02   | P1       | REQUESTED | AGENT  | supervisor-agent | 2026-10-27T21:00:20.025Z
update_postimage | 1          | CNC-02   | P1       | APPROVED  | AGENT  | supervisor-agent | 2026-10-27T21:04:35.759Z
```

## Supervisor actions (gold_supervisor_actions, reverse-synced from Lakebase)

```
action_id | asset_id | action            | acted_by              | acted_at                 | work_order_request_id | note                                                        
----------+----------+-------------------+-----------------------+--------------------------+-----------------------+-------------------------------------------------------------
1         | CNC-02   | ACKNOWLEDGE       | setup-smoke-test      | 2026-10-19T19:17:26.956Z | None                  | setup smoke test of the Lakebase write path                 
2         | CNC-02   | ACKNOWLEDGE       | setup-smoke-test      | 2026-10-19T19:18:47.925Z | None                  | setup smoke test of the Lakebase write path                 
3         | CNC-02   | CREATE_WORK_ORDER | supervisor-agent      | 2026-10-27T21:00:20.048Z | 1                     | spindle bearing replacement                                 
4         | CNC-02   | ACKNOWLEDGE       | n.raam@databricks.com | 2026-10-27T21:04:35.488Z | None                  | Reviewed at handover; bearing replacement planned at next st
5         | CNC-02   | ACKNOWLEDGE       | n.raam@databricks.com | 2026-10-27T21:44:52.431Z | None                  | Handover review after rebuild; bearing replacement planned a
```

## KPI — alert -> first action (gold_alert_response)

```
asset_id | scored_shift_id | risk_score | at_risk | alert_raised_at          | first_action | first_actor           | first_action_at          | actions | minutes_to_first_action
---------+-----------------+------------+---------+--------------------------+--------------+-----------------------+--------------------------+---------+------------------------
CNC-02   | 2026-10-18-C    | 0.9981     | true    | 2026-10-27T21:42:46.600Z | ACKNOWLEDGE  | n.raam@databricks.com | 2026-10-27T21:44:52.431Z | 1       | 2.1                    
```
