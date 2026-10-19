#!/usr/bin/env bash
# Pre-demo health check. Verifies data, resource states, and (optionally) the
# app + agent round-trip. Customize the [DATA] section per project.
# Usage: ./healthcheck.sh
set -uo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck disable=SC1091
source "$HERE/config.env"

pass=0; fail=0
ok()  { echo "  ✅ $1"; pass=$((pass+1)); }
bad() { echo "  ❌ $1"; fail=$((fail+1)); }

sqlq() { # run SQL against the schema, echo first-row first-col
  databricks api post /api/2.0/sql/statements -p "$PROFILE" --json \
    "{\"warehouse_id\":\"$WAREHOUSE_ID\",\"catalog\":\"$CATALOG\",\"schema\":\"$SCHEMA\",\"statement\":\"$1\",\"wait_timeout\":\"50s\"}" 2>/dev/null \
    | python3 -c "import json,sys;d=json.load(sys.stdin);r=d.get('result',{}).get('data_array');print(r[0][0] if r else 'ERR:'+str(d.get('status',{}).get('state')))" 2>/dev/null
}

echo "=== $SCHEMA health check ($(date '+%Y-%m-%d %H:%M')) ==="

echo "[DATA] schema populated (customize these checks per project)"
n=$(sqlq "SELECT count(*) FROM information_schema.tables WHERE table_schema='$SCHEMA'")
[ "${n:-0}" -ge 1 ] 2>/dev/null && ok "tables in $SCHEMA: $n" || bad "no tables found in $CATALOG.$SCHEMA"

echo "[WAREHOUSE]"
ws=$(databricks warehouses get "$WAREHOUSE_ID" -p "$PROFILE" -o json 2>/dev/null | python3 -c "import json,sys;print(json.load(sys.stdin).get('state','?'))" 2>/dev/null)
{ [ "$ws" = "RUNNING" ] || [ "$ws" = "STARTING" ]; } && ok "warehouse: $ws" || bad "warehouse: $ws (run manage.sh start)"

echo "[APP]"
app=$(databricks apps get "$APP_NAME" -p "$PROFILE" -o json 2>/dev/null | python3 -c "import json,sys;d=json.load(sys.stdin);print(d.get('compute_status',{}).get('state','?'),d.get('url',''))" 2>/dev/null)
[ -n "$app" ] && ok "app: $app" || bad "app not deployed/reachable"

if [ -n "${SUPERVISOR_ENDPOINT:-}" ]; then
  echo "[SERVING ENDPOINT]"
  s=$(databricks serving-endpoints get "$SUPERVISOR_ENDPOINT" -p "$PROFILE" -o json 2>/dev/null | python3 -c "import json,sys;print(json.load(sys.stdin).get('state',{}).get('ready','?'))" 2>/dev/null)
  [ "$s" = "READY" ] && ok "endpoint: $s" || bad "endpoint: $s"
fi

echo "-----------------------------------------------"
echo "RESULT: $pass passed, $fail failed"
[ "$fail" -eq 0 ] && echo "✅ Ready for demo" || echo "⚠ Fix the ❌ items before demoing"
