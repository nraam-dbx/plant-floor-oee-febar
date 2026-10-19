#!/usr/bin/env bash
# Stage 4 · Reverse sync Lakebase -> Unity Catalog: change data feed for every table in Postgres schema `ops`
# materialized as Delta tables in ${CATALOG}.${SCHEMA}. Beta API, not yet a bundle resource. Idempotent.
set -euo pipefail
cd "$(dirname "$0")/.." && source config.env
DB="projects/plant-floor-oee-febar/branches/production/databases/databricks-postgres"
if databricks postgres list-cdf-configs "$DB" -p "$PROFILE" -o json 2>/dev/null | jq -e '.[]? | select(.postgres_schema=="ops" or .spec.postgres_schema=="ops")' >/dev/null; then
  echo "cdf config for ops already exists"
else
  databricks postgres create-cdf-config "$DB" "$CATALOG" "$SCHEMA" ops --cdf-config-id ops_to_uc -p "$PROFILE" -o json
fi
databricks postgres list-cdf-statuses "$DB" -p "$PROFILE" -o json 2>/dev/null || true
