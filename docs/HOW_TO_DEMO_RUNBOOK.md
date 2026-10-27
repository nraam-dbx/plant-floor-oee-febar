# How to Demo — Runbook

**Project:** plant_floor_oee_febar

## 1. What this is
Plant-floor OEE for a turbine-component plant: IT (ERP/MES/CMMS) and OT (historian/SCADA) data joined on one asset key,
a next-shift OEE-at-risk model, an Agent Bricks agent over Genie + manuals, and an app where supervisors act. For an
exec sponsor (VP Manufacturing Operations) and a domain owner (Plant Reliability & Maintenance Engineering Manager).

## 2. Environment
| | |
|---|---|
| Workspace | https://fevm-nraameast1.cloud.databricks.com |
| Catalog / schema | `nraameast1_catalog.plant_floor_oee_febar` |
| Warehouse | `ba24ff79986686a9` |
| CLI profile | `fevm-nraameast1` |
| App | `plant-floor-oee-febar` → https://plant-floor-oee-febar-7474650251978703.aws.databricksapps.com |
| Lakebase | project `plant-floor-oee-febar` (db `databricks_postgres`) |
| Genie space | Plant OEE Analyst `01f1d23e18d51bf08e7219f0e2204db1` |
| Supervisor agent | Plant-Floor OEE Agent, endpoint `mas-9960e05a-endpoint` |

Run `ops/*.sh` from the project root.

## 3. Build / setup order (one-time)
See the **Rebuild from scratch** block in the repository `README.md` (bundle deploy → build job → Lakebase setup →
reverse sync → UC functions + Genie → Agent Bricks → app + post-deploy grants → eval).

## 4. How to demo — run order
### Pre-flight
```bash
ops/manage.sh start
ops/manage.sh status
ops/healthcheck.sh
```
Then republish the alert so the alert → action KPI starts now:
`databricks bundle run plant_oee_build --only genai_root_cause,refresh_lakebase_sync`, and ask the agent one question
in the app to warm the endpoints.
### In the app
Follow `docs/DEMO_SCRIPT.md`: KPI tiles → at-risk queue (CNC-02) → agent "what should I do" → agent raises a work
order (approve the tool call) → approve the request + Acknowledge → Genie question → Catalog Explorer (lineage, tags,
masks) → `gold_alert_response`.

### Tear-down (keep costs at zero)
```bash
ops/manage.sh stop
```

## 5. Giving others access to demo this
- **Watch:** you present / screen-share — nothing to grant.
- **Click through the app:** workspace user + app `plant-floor-oee-febar` → `CAN_USE`. (App reads data as its own SP, so no per-user UC grants needed.)
- **Co-present / run ops:** + CLI auth (below) + app `CAN_MANAGE` + warehouse `CAN_USE` (+ job `CAN_MANAGE_RUN` for any ingest jobs). UC `GRANT SELECT`/`EXECUTE` only for direct SQL/Genie.

### CLI auth (a colleague, on their own machine)
Prerequisite: they already have workspace access.
```bash
brew tap databricks/tap && brew install databricks     # need v0.285.0+
databricks auth login --host https://fevm-nraameast1.cloud.databricks.com --profile fevm-nraameast1
databricks current-user me -p fevm-nraameast1               # prints THEIR email
```
Name the profile exactly `fevm-nraameast1` (the ops scripts hardcode it). They authenticate as
themselves via SSO — never share `~/.databrickscfg` or a PAT; a `403` means a missing grant.

## 6. Supporting collateral
| Artifact | Path |
|---|---|
| Demo script | `docs/DEMO_SCRIPT.md` |
| Business deck | `docs/FEBAR_business_deck.pdf` (source `docs/deck/`, Google Slides link in `CLAUDE.md`) |
| Value model | `docs/deck/VALUE_MODEL.md` |
| Evidence | `evidence/README.md` |

## 7. Gotchas
- Workspace is serverless-only; jobs and notebooks never request clusters.
- Agent answers that call 3+ tools take ~40–100 s; warm the agent before presenting.
- Agent → app MCP tool calls pause for approval (`mcp_approval_request`); the app's chat shows Approve / Reject.
- The app's SP needs `CAN_USE` on its own app for the MCP tool (`ops/app_post_deploy.sh`).
- Lakebase compute suspends after 5 min idle; the first query after a pause takes a few seconds.
- CLI OAuth expires after about a week idle: `databricks auth login --profile fevm-nraameast1`.
- Full project notes and every issue hit during the build: `CLAUDE.md`.
