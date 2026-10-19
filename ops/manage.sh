#!/usr/bin/env bash
# Start/stop/status the billable resources for this demo, + sync collateral.
# Usage: ./manage.sh start | stop | status | sync
# Serving endpoints + Lakebase scale to zero when idle, so start/stop focus on
# the app + warehouse. Extend the ingest-* pattern below if you add streaming.
set -uo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck disable=SC1091
source "$HERE/config.env"

db() { databricks "$@" -p "$PROFILE"; }
cmd="${1:-status}"

case "$cmd" in
  start)
    echo "▶ Starting SQL warehouse..."
    [ -n "$WAREHOUSE_ID" ] && db warehouses start "$WAREHOUSE_ID" 2>&1 | head -2 || echo "  (WAREHOUSE_ID not set)"
    echo "▶ Starting app $APP_NAME..."
    db apps start "$APP_NAME" 2>&1 | head -3 || echo "  (app may already be running or not yet deployed)"
    echo "ℹ Serving endpoints + Lakebase warm up on first request (scale-to-zero)."
    ;;
  stop)
    echo "⏹ Stopping app $APP_NAME..."
    db apps stop "$APP_NAME" 2>&1 | head -3 || true
    echo "⏹ Stopping SQL warehouse..."
    [ -n "$WAREHOUSE_ID" ] && db warehouses stop "$WAREHOUSE_ID" 2>&1 | head -2 || true
    echo "ℹ Serving endpoints + Lakebase will auto-suspend when idle."
    ;;
  status)
    echo "=== $SCHEMA resource status ==="
    echo -n "SQL warehouse : "
    db warehouses get "$WAREHOUSE_ID" -o json 2>/dev/null | python3 -c "import json,sys;print(json.load(sys.stdin).get('state','?'))" 2>/dev/null || echo "?"
    echo -n "App           : "
    db apps get "$APP_NAME" -o json 2>/dev/null | python3 -c "import json,sys;d=json.load(sys.stdin);print(d.get('compute_status',{}).get('state', d.get('app_status',{}).get('state','?')),'|',d.get('url','(no url)'))" 2>/dev/null || echo "not deployed yet"
    if [ -n "${SUPERVISOR_ENDPOINT:-}" ]; then
      echo -n "Serving ep    : "
      db serving-endpoints get "$SUPERVISOR_ENDPOINT" -o json 2>/dev/null | python3 -c "import json,sys;print(json.load(sys.stdin).get('state',{}).get('ready','?'))" 2>/dev/null || echo "?"
    fi
    ;;
  sync)
    exec "$HERE/ops/sync.sh"
    ;;
  *)
    echo "Usage: $0 start|stop|status|sync"
    exit 1;;
esac
