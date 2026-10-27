#!/usr/bin/env bash
# Stage 6 · One-time post-deploy steps for the app (idempotent):
#  1. Postgres least-privilege grants for the app SP role (lakebase/03_app_grants.sql via the setup job)
#  2. CAN_USE for the app SP on its own app, so the Supervisor's MCP tool call (made as that SP) is authorized
set -euo pipefail
cd "$(dirname "$0")/.." && source config.env
SP=$(databricks apps get "$APP_NAME" -p "$PROFILE" -o json | jq -r .service_principal_client_id)
JOB=$(databricks bundle summary -o json | jq -r '.resources.jobs.plant_oee_lakebase_setup.id')
databricks jobs run-now --json "{\"job_id\":$JOB,\"notebook_params\":{\"smoke_test\":\"false\",\"app_role\":\"$SP\"}}" -p "$PROFILE" -o json | jq -r '"grants run: \(.run_id) \(.state.result_state)"'
databricks apps update-permissions "$APP_NAME" -p "$PROFILE" -o json \
  --json "{\"access_control_list\":[{\"service_principal_name\":\"$SP\",\"permission_level\":\"CAN_USE\"}]}" >/dev/null && echo "app SP $SP: CAN_USE on $APP_NAME"
