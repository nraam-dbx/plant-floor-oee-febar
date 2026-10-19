# How to Demo — Runbook

**Project:** plant_floor_oee_febar

## 1. What this is
<!-- 2–3 sentences: the story and who it's for. -->

## 2. Environment
| | |
|---|---|
| Workspace | https://fevm-nraameast1.cloud.databricks.com |
| Catalog / schema | `nraameast1_catalog.plant_floor_oee_febar` |
| Warehouse | `ba24ff79986686a9` |
| CLI profile | `fevm-nraameast1` |
| App | `plant-floor-oee-febar` |

Run `ops/*.sh` from the project root.

## 3. Build / setup order (one-time)
1. `notebooks/` — tables + volumes
2. `data_generation/` — synthetic data
3. `pipeline/` — medallion
4. `agents/` — UC functions, Genie/Agent Bricks, governance
5. `app/` — deploy
6. live/streaming extras (if any)

## 4. How to demo — run order
### Pre-flight
```bash
ops/manage.sh start
ops/manage.sh status
ops/healthcheck.sh
```
### In the app
<!-- The tab-by-tab story. -->

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
| Diagrams | `docs/*.drawio` |

## 7. Gotchas
<!-- Log per-project quirks here. -->
