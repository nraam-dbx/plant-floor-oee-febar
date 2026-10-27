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

n=$(sqlq "SELECT count(*) FROM gold_at_risk_queue WHERE at_risk")
[ "${n:-0}" -ge 1 ] 2>/dev/null && ok "at-risk assets in queue: $n" || bad "no at-risk asset in gold_at_risk_queue (run the build job)"
n=$(sqlq "SELECT count(*) FROM gold_oee_shift")
[ "${n:-0}" -ge 1000 ] 2>/dev/null && ok "gold_oee_shift rows: $n" || bad "gold_oee_shift rows: $n"

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

echo "[APP → LAKEBASE]"
url=$(databricks apps get "$APP_NAME" -p "$PROFILE" -o json 2>/dev/null | python3 -c "import json,sys;print(json.load(sys.stdin).get('url',''))" 2>/dev/null)
tok=$(databricks auth token -p "$PROFILE" -o json 2>/dev/null | python3 -c "import json,sys;print(json.load(sys.stdin)['access_token'])" 2>/dev/null)
h=$(curl -s -m 60 -H "Authorization: Bearer $tok" "$url/api/health" 2>/dev/null)
echo "$h" | grep -q '"lakebase":true' && ok "app health: $h" || bad "app health: ${h:-no response} (Lakebase may be waking up — retry)"

echo "-----------------------------------------------"
echo "RESULT: $pass passed, $fail failed"
[ "$fail" -eq 0 ] && echo "✅ Ready for demo" || echo "⚠ Fix the ❌ items before demoing"
